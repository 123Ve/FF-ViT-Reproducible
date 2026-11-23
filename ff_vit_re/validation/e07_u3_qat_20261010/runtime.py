"""Original E07 finite-width execution; analytic backward proxies only.

Original E07 sources are never imported as mutable engineering outputs.
Integer software execution is not an RTL or board validation result.
"""
from __future__ import annotations
import copy
import math
import sys
from pathlib import Path
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path[:0]=[str(ROOT/'validation/softmax_u3_hls_20261010'),str(ROOT)]
import u3_validation as u
exact=u.exact

class ExactSTE(torch.autograd.Function):
    @staticmethod
    def forward(ctx,proxy,codes):
        return codes.to(dtype=proxy.dtype)
    @staticmethod
    def backward(ctx,gradient):
        return gradient,None

def ste(proxy,codes):
    return ExactSTE.apply(proxy,codes.detach())

def head_intermediates(value,p):
    x=exact.wrap(value,13)
    m,shift,bias,address_shift,bound,affine_shift,bits=map(int,p['scalars'][:7])
    acc=exact.wrap(x.sum(-1),15,False)
    product=exact.wrap(acc*m,30,False)
    rounded=exact.wrap(product+(1 << (shift-1)),30,False)
    mean=exact.wrap(rounded >> shift,7,False)
    diff=exact.wrap(x-mean.unsqueeze(-1),13)
    variance=exact.wrap((diff*diff).sum(-1),24,False)
    address=exact.wrap((variance+bias) >> address_shift,6,False).clamp(0,bound)
    rsqrt=exact.wrap(exact.integer(p['rsqrt_table'],x.device),11,False)[address]
    affine=exact.wrap(diff*rsqrt.unsqueeze(-1)*exact.integer(p['lnw'],x.device)+exact.integer(p['lnb'],x.device),36)
    shifted=exact.wrap(affine >> affine_shift,9)
    return dict(sum=acc,product=product,round_add=rounded,mean=mean,diff=diff,
        variance=variance,address=address,rsqrt=rsqrt,affine=affine,
        codes=shifted.clamp(-(1 << (bits-1)),(1 << (bits-1))-1))

def head_layernorm(value,p):
    return head_intermediates(value,p)['codes']

def integer_forward(images,artifact,trace=False):
    records={}
    x=exact.patch_forward(images,artifact['patch'])
    if trace:records['patch']=x.clone()
    for b,p in enumerate(artifact['blocks']):
        x,t=exact.block_forward(x,p,trace=trace)
        records.update({f'block{b:02d}.{k}':v for k,v in t.items()})
    h=artifact['head']
    p=dict(scalars=h['head_ln_scalars'][:7],lnw=h['head_lnw'],lnb=h['head_lnb'],rsqrt_table=h['head_rsqrt'])
    norm=head_layernorm(x[:,0],p)
    logits=exact.wrap(exact.matmul(norm,exact.integer(h['head_weight'],x.device).t())+exact.integer(h['head_bias'],x.device),19)
    if trace:records.update(head_ln=norm,logits=logits)
    return logits,records

def state_value(state,suffix):
    keys=[k for k in state if k.endswith(suffix)]
    if len(keys)!=1:raise ValueError(f'nonunique checkpoint binding: {suffix}')
    return state[keys[0]].detach().float()

def frozen(module,name,value):
    module.register_buffer(name,torch.as_tensor(value).clone())

def int_codes(value):
    return value.detach().round().to(torch.int64)

class CodeLinear(nn.Module):
    """Train original real master weights; export a bounded integer matrix.

    threshold_gain is a learned rounding threshold, NOT an inserted post-MAC
    requantizer. Physical code scales in the export contract remain fixed.
    A frozen integer offset reconciles the master checkpoint with its separately
    fitted historical deployment code. This offset is recorded in state_dict.
    """
    def __init__(self,weight,bias,weight_scale,domain,codes,bias_codes,bits,weight_bits=3):
        super().__init__()
        self.master=nn.Parameter(weight.clone())
        self.bias=nn.Parameter(bias.clone())
        self.threshold_gain=nn.Parameter(torch.tensor(0.))
        self.bits=bits;self.weight_bits=weight_bits;self.domain=float(domain)
        frozen(self,'weight_scale',torch.tensor(float(weight_scale)))
        frozen(self,'offset',torch.as_tensor(codes).long()-torch.round(weight/weight_scale).long())
        frozen(self,'initial_bias',bias)
        frozen(self,'bias_codes',torch.as_tensor(bias_codes).long())

    def codes(self):
        divisor=self.weight_scale*self.threshold_gain.exp()
        z=self.master/divisor+self.offset
        lo=-(1 << (self.weight_bits-1));hi=(1 << (self.weight_bits-1))-1
        actual=z.detach().round().clamp(lo,hi).long()
        w=ste(z.clamp(lo,hi),actual)
        bproxy=(self.bias-self.initial_bias)/self.domain+self.bias_codes
        b=ste(bproxy,exact.wrap(self.bias_codes+torch.round((self.bias-self.initial_bias).detach().double()/self.domain).long(),self.bits))
        return w,b

    def forward(self,x):
        w,b=self.codes()
        proxy=F.linear(x,w,b)
        with torch.no_grad():
            actual=exact.wrap(exact.matmul(int_codes(x),int_codes(w).t())+int_codes(b),self.bits)
        return ste(proxy,actual)

    def export(self):
        with torch.no_grad():
            w,b=self.codes()
            return int_codes(w).cpu().numpy().astype(np.int8),int_codes(b).cpu().numpy().astype(np.int32)

class CodeNorm(nn.Module):
    def __init__(self,p,gamma,beta,input_scale,output_scale,input_bits,head=False):
        super().__init__()
        self.scalars=np.array(p['scalars']).copy();self.input_bits=input_bits;self.head=head
        self.input_scale=float(input_scale);self.output_scale=float(output_scale)
        self.gamma=nn.Parameter(torch.as_tensor(gamma).float().clone())
        self.beta=nn.Parameter(torch.as_tensor(beta).float().clone())
        frozen(self,'initial_gamma',self.gamma.detach());frozen(self,'initial_beta',self.beta.detach())
        frozen(self,'lnw',np.asarray(p['lnw']).astype(np.int64))
        frozen(self,'lnb',np.asarray(p['lnb']).astype(np.int64))
        frozen(self,'rsqrt_table',np.asarray(p['rsqrt_table']).astype(np.int64))

    def parameters_int(self):
        denominator=torch.where(self.initial_gamma.abs()>1e-8,self.initial_gamma,torch.ones_like(self.initial_gamma))
        delta=torch.round(self.lnw.double()*(self.gamma.detach().double()-self.initial_gamma.double())/denominator.double()).long()
        weight=exact.wrap(self.lnw+delta,32)
        bias=self.lnb+torch.round((self.beta.detach().double()-self.initial_beta.double())/self.output_scale*(1 << int(self.scalars[5]))).long()
        return dict(scalars=self.scalars,lnw=weight,lnb=bias,rsqrt_table=self.rsqrt_table)

    def forward(self,x):
        proxy=F.layer_norm(x*self.input_scale,(192,),self.gamma,self.beta,1e-6)/self.output_scale
        with torch.no_grad():
            p=self.parameters_int()
            actual=head_layernorm(int_codes(x),p) if self.head else exact.layernorm(int_codes(x),p,input_bits=self.input_bits)
        return ste(proxy,actual)

    def export(self):
        p=self.parameters_int()
        return {k:v.detach().cpu().numpy() if torch.is_tensor(v) else v.copy() for k,v in p.items()}

class CodeLUT(nn.Module):
    """One scalar table gain; exported table still has exactly64 original codes."""
    def __init__(self,p,cursor_bits,output_bits,signed=True):
        super().__init__()
        self.scalars=np.array(p['scalars']).copy();self.cursor_bits=cursor_bits
        self.output_bits=output_bits;self.signed=signed
        frozen(self,'table',np.asarray(p['table']).astype(np.int64))
        self.threshold_gain=nn.Parameter(torch.tensor(0.))

    def codes(self):
        lo=-(1 << (self.output_bits-1)) if self.signed else 0
        hi=(1 << (self.output_bits-int(self.signed)))-1
        return torch.round(self.table.double()*self.threshold_gain.detach().double().exp()).clamp(lo,hi).long()

    def forward(self,x,proxy):
        with torch.no_grad():actual=exact.address_lut(int_codes(x),self.scalars,self.codes(),self.cursor_bits)
        return ste(proxy*self.threshold_gain.exp(),actual)

    def export(self):
        return dict(scalars=self.scalars.copy(),table=self.codes().cpu().numpy())

class CodeSoftmax(nn.Module):
    def __init__(self,p,score_scale):
        super().__init__()
        self.scalars=np.array(p['scalars']).copy()
        if int(self.scalars[13])!=3:raise ValueError('strict E07 probability output must be U3')
        self.score_scale=float(score_scale);self.output_scale=float(p.get('output_scale',1/256))
        frozen(self,'exp_table',np.asarray(p['exp']).astype(np.int64))
        frozen(self,'recip1',np.asarray(p['recip1']).astype(np.uint8).astype(np.int64))
        frozen(self,'recip2',np.asarray(p['recip2']).astype(np.uint8).astype(np.int64))
        self.threshold_gain=nn.Parameter(torch.tensor(0.))

    def tables(self):
        gain=self.threshold_gain.detach().double().exp()
        return [torch.round(t.double()*gain).clamp(0,255).long() for t in (self.recip1,self.recip2)]

    def forward(self,scores):
        proxy=(torch.softmax(scores*self.score_scale,-1)/self.output_scale*self.threshold_gain.exp()).clamp(0,7)
        with torch.no_grad():
            actual=exact.fused_softmax(int_codes(scores),self.scalars,self.exp_table,*self.tables())
        return ste(proxy,actual)

    def export(self):
        t=self.tables()
        return dict(scalars=self.scalars.copy(),exp=self.exp_table.cpu().numpy().astype(np.uint16),
            recip1=t[0].cpu().numpy().astype(np.uint8),recip2=t[1].cpu().numpy().astype(np.uint8).view(np.int8),
            output_scale=self.output_scale)

class CodeBlock(nn.Module):
    def __init__(self,b,p,state,ref):
        super().__init__();self.ref=copy.deepcopy(ref);self.original=copy.deepcopy(p)
        def sv(name):return state_value(state,f'blocks.{b}.{name}')
        self.norms=nn.ModuleList([CodeNorm(p[f'ln{j+1}'],sv(f'norm{j+1}.weight'),sv(f'norm{j+1}.bias'),
            ref['ln'][j]['input_scale'],ref['ln'][j]['output_scale'],ref['ln'][j]['input_bits']) for j in range(2)])
        self.linears=nn.ModuleDict();self.luts=nn.ModuleDict()
        names=[('q','attn.qkv',12,0),('k','attn.qkv',11,1),('v','attn.qkv',11,2),
            ('o','attn.proj',13,None),('m1','mlp.fc1',11,None),('m2','mlp.fc2',13,None)]
        self.domains={}
        for name,source,bits,part in names:
            w,bias,sc=sv(source+'.weight'),sv(source+'.bias'),sv(source+'.log_scale').exp()
            if part is not None:w=w[part*192:(part+1)*192];bias=bias[part*192:(part+1)*192];scale=float(sc[part])
            else:scale=float(sc[0])
            activation=ref['ln'][0 if name in ('q','k','v') else 1]['output_scale']
            if name=='o':activation=ref['a_scale']
            if name=='m2':activation=ref['gelu_output_scale']
            domain=activation*scale;self.domains[name]=domain
            self.linears[name]=CodeLinear(w,bias,scale,domain,p[name+'_w'],p[name+'_b'],bits)
        for name in ('q','k','v','a','gelu'):
            self.luts[name]=CodeLUT(p[name+'_lut'],32 if name=='gelu' else (10 if name=='a' else 9),3,name!='gelu')
        self.softmax=CodeSoftmax(p['softmax'],ref['score_scale'])

    def residual(self,x,main,sc,bits):
        shift=int(sc[1]);multiplier=int(sc[0])
        proxy=main+x*(multiplier/(1 << shift))
        with torch.no_grad():actual=exact.residual(int_codes(x),int_codes(main),sc,bits)
        return ste(proxy,actual)

    def forward(self,x):
        ln=self.norms[0](x);qkv=[]
        for name in ('q','k','v'):
            raw=self.linears[name](ln)
            value=self.luts[name](raw,(raw*self.domains[name]/self.ref[name+'_scale']).clamp(-4,3))
            qkv.append(value.reshape(-1,196,3,64).permute(0,2,1,3))
        q,k,v=qkv
        scores=q@k.transpose(-1,-2)
        probability=self.softmax(scores)
        raw=probability@v
        with torch.no_grad():actual=exact.wrap(exact.matmul(int_codes(probability),int_codes(v)),11)
        raw=ste(raw,actual)
        a=self.luts['a'](raw,(raw*self.softmax.output_scale*self.ref['v_scale']/self.ref['a_scale']).clamp(-4,3))
        a=a.permute(0,2,1,3).reshape(-1,196,192)
        o=self.linears['o'](a)
        skip=self.residual(x,o,self.original['attn_residual'],15)
        ln2=self.norms[1](skip)
        m1=self.linears['m1'](ln2)
        ge=self.luts['gelu'](m1,(F.gelu(m1*self.ref['gelu_input_scale'])/self.ref['gelu_output_scale']).clamp(0,7))
        m2=self.linears['m2'](ge)
        return self.residual(skip,m2,self.original['mlp_residual'],13)

    def export(self):
        p=copy.deepcopy(self.original)
        for j,norm in enumerate(self.norms):p[f'ln{j+1}']=norm.export()
        for name,linear in self.linears.items():p[name+'_w'],p[name+'_b']=linear.export()
        for name,lut in self.luts.items():p[name+'_lut']=lut.export()
        p['softmax']=self.softmax.export()
        return p

class StrictQAT(nn.Module):
    def __init__(self,artifact,state,reference,classes,head_scales=None):
        super().__init__();self.original=copy.deepcopy(artifact);self.classes=classes
        self.reference=copy.deepcopy(reference)
        for b,r in enumerate(self.reference):
            for name in ('q','k'):
                if name+'_scale' not in r:
                    raise ValueError('original Q/K scales must be bound explicitly')
        self.blocks=nn.ModuleList([CodeBlock(b,p,state,self.reference[b]) for b,p in enumerate(artifact['blocks'])])
        if head_scales is None:
            raise ValueError('original Head scales must be bound explicitly')
        self.head_scales=head_scales
        h=artifact['head']
        hp=dict(scalars=h['head_ln_scalars'][:7],lnw=h['head_lnw'],lnb=h['head_lnb'],rsqrt_table=h['head_rsqrt'])
        self.head_norm=CodeNorm(hp,state_value(state,'vit.norm.weight'),state_value(state,'vit.norm.bias'),
            self.blocks[-1].domains['m2'],head_scales['ln'],13,True)
        headw=state_value(state,'vit.head.weight');headb=state_value(state,'vit.head.bias')
        self.head_master=nn.Parameter(headw.clone());self.head_bias=nn.Parameter(headb.clone())
        self.head_threshold_gain=nn.Parameter(torch.tensor(0.))
        frozen(self,'initial_head_bias',headb)
        frozen(self,'head_weight_offset',torch.as_tensor(h['head_weight'][:classes]).long()-torch.round(headw/head_scales['weight']).long())
        frozen(self,'head_bias_codes',np.asarray(h['head_bias'][:classes]).astype(np.int64))
        self.logit_scale=float(head_scales['ln']*head_scales['weight'])

    def head_codes(self):
        proxy=self.head_master/(self.head_scales['weight']*self.head_threshold_gain.exp())+self.head_weight_offset
        weight=ste(proxy.clamp(-128,127),proxy.detach().round().clamp(-128,127).long())
        bproxy=(self.head_bias-self.initial_head_bias)/self.logit_scale+self.head_bias_codes
        bcode=exact.wrap(self.head_bias_codes+torch.round((self.head_bias-self.initial_head_bias).detach().double()/self.logit_scale).long(),19)
        return weight,ste(bproxy,bcode)

    def forward(self,images):
        x=exact.patch_forward(images,self.original['patch']).float()
        for block in self.blocks:x=block(x)
        norm=self.head_norm(x[:,0]);w,b=self.head_codes()
        proxy=F.linear(norm,w,b)
        with torch.no_grad():active=exact.wrap(exact.matmul(int_codes(norm),int_codes(w).t())+int_codes(b),19)
        active=ste(proxy,active)
        # Preserve original1000 logits and inactive-class sentinel.
        padding=self.original['head']['head_bias'][self.classes:]
        pad=torch.as_tensor(padding,device=active.device,dtype=active.dtype).expand(len(active),-1)
        return torch.cat((active,pad),-1)

    def set_progressive(self,epoch):
        first=6 if epoch==0 else (3 if epoch==1 else 0)
        for b,block in enumerate(self.blocks):
            for parameter in block.parameters():parameter.requires_grad_(b>=first)
        return list(range(first,12))

    def optimizer_groups(self,lr=1e-5,scale_lr=1e-4):
        gains=[];normal=[]
        for name,p in self.named_parameters():
            (gains if 'threshold_gain' in name else normal).append(p)
        return [dict(params=normal,lr=lr,weight_decay=.01),dict(params=gains,lr=scale_lr,weight_decay=0.)]

    def export(self):
        a=copy.deepcopy(self.original);a['blocks']=[p.export() for p in self.blocks]
        h=a['head'];norm=self.head_norm.export()
        h['head_lnw']=norm['lnw'];h['head_lnb']=norm['lnb']
        w,b=self.head_codes()
        h['head_weight'][:self.classes]=int_codes(w).cpu().numpy()
        h['head_bias'][:self.classes]=int_codes(b).cpu().numpy()
        return a

    def error_reference(self):
        result=copy.deepcopy(self.reference)
        for b,block in enumerate(self.blocks):
            for j,norm in enumerate(block.norms):
                result[b]['ln'][j]['gamma']=norm.gamma.detach().cpu().numpy()
                result[b]['ln'][j]['beta']=norm.beta.detach().cpu().numpy()
        return result
