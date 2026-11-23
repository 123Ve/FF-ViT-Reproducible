"""Teacher-detached logit and normalized intermediate feature distillation."""
import torch
import torch.nn.functional as F


def logit_kd(student, teacher, *, temperature=2.):
    return F.kl_div(F.log_softmax(student.float() / temperature, dim=-1),
                    F.softmax(teacher.detach().float() / temperature, dim=-1),
                    reduction='batchmean') * temperature ** 2


def feature_reconstruction(student, teacher):
    if student.keys() != teacher.keys() or not student:
        raise ValueError('feature sets must be nonempty and identical')
    values = []
    for key, value in student.items():
        target = teacher[key].detach().float()
        values.append((value.float() - target).square().mean() / target.square().mean().clamp_min(1e-6))
    return torch.stack(values).mean()
