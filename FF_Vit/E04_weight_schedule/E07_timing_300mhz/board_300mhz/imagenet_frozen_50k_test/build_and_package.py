"""Compile PS only, reuse every accepted PL/model/firmware byte, package BOOT.BIN."""
import csv
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parent
BOARD=ROOT.parent
E07=BOARD.parent
ACCEPTED=BOARD/"deploy"
DEPLOY=ROOT/"deploy"
BSP=BOARD/"workspace/e07_platform/export/e07_platform/sw/standalone_psu_cortexa53_0"
TOOL=Path("/opt/vivado/2025.1/Vitis/gnu/aarch64/lin/aarch64-none/bin")
BUILD=ROOT/"build"
EXPECTED_BIT="2fedb6d70a0916fc9aebfdf3141008690685c0dbd1b5bab0ae58821564ef1037"
EXPECTED_WEIGHTS="0fac7e4cd09ae8367e5c8dfd5cb469473780055feccf9569a8376419028e2cd7"


def digest(p):
    with Path(p).open("rb") as s: return hashlib.file_digest(s,"sha256").hexdigest()


def snapshot():
    paths=list((E07/"src").glob("*.h"))+list((E07/"src").glob("*.cpp"))
    paths.extend(p for p in ACCEPTED.iterdir() if p.is_file())
    paths.extend(p for p in (E07/"inputs").iterdir() if p.is_file())
    return {str(p.resolve()):digest(p) for p in sorted(set(paths))}


def verify_deployment(folder):
    folder=Path(folder)
    identity=json.loads((folder/"identity.json").read_text())
    for path,h in identity["frozen_files"].items():
        if digest(path)!=h: raise ValueError(f"frozen file changed: {path}")
    for name,item in identity["deployment_files"].items():
        p=folder/name
        if p.stat().st_size!=item["bytes"] or digest(p)!=item["sha256"]:
            raise ValueError(f"deployment file changed: {name}")
    if digest(folder/"design_1_wrapper.bit")!=EXPECTED_BIT or digest(folder/"weights.bin")!=EXPECTED_WEIGHTS:
        raise ValueError("wrong PL/model identity")
    data=json.loads((folder/"dataset_identity.json").read_text())
    for name,item in data["files"].items():
        if (folder/name).stat().st_size!=item["bytes"] or digest(folder/name)!=item["sha256"]:
            raise ValueError(f"dataset changed: {name}")
    return {"status":"PASS","frozen_files_checked":len(identity["frozen_files"]),
            "deployment_files_checked":len(identity["deployment_files"]),"dataset_frames":data["count"],
            "bitstream_sha256":EXPECTED_BIT,"weights_sha256":EXPECTED_WEIGHTS,
            "board_accuracy_status":"not measured; run on board"}


def main():
    if digest(ACCEPTED/"design_1_wrapper.bit")!=EXPECTED_BIT or digest(ACCEPTED/"weights.bin")!=EXPECTED_WEIGHTS:
        raise RuntimeError("accepted identity mismatch")
    if BUILD.exists() or (DEPLOY/"BOOT.BIN").exists():
        raise FileExistsError("refusing to overwrite previous build/boot image")
    data=json.loads((DEPLOY/"dataset_identity.json").read_text())
    if data["status"]!="READY_FOR_BOARD_TEST_NOT_MEASURED": raise RuntimeError("dataset not complete")
    before=snapshot()
    BUILD.mkdir()
    linker=BUILD/"lscript.ld"
    shutil.copy2(BOARD/"workspace/e07_inference/src/lscript.ld",linker)
    gcc=str(TOOL/"aarch64-none-elf-gcc")
    flags=["-DSDT",f"-specs={BSP/'Xilinx.spec'}",f"-I{BSP/'include'}",f"-I{BOARD/'src'}",
           f"-I{ROOT/'src'}","-std=gnu11","-Wall","-Wextra","-Werror","-O0","-g3","-U__clang__"]
    obj=BUILD/"main.o"
    elf=BUILD/"e07_image_accuracy.elf"
    commands=[
        [gcc,*flags,"-c",str(ROOT/"src/main.c"),"-o",str(obj)],
        [gcc,*flags,str(obj),"-o",str(elf),f"-Wl,-T,{linker}",f"-L{BSP/'lib'}",
         f"-Wl,-Map,{BUILD/'e07_image_accuracy.map'}","-Wl,--start-group",
         "-lxilstandalone","-lxiltimer","-lxilffs","-lxil","-lgcc","-lc","-Wl,--end-group"],
        [str(TOOL/"aarch64-none-elf-size"),str(elf)]]
    (BUILD/"commands.json").write_text(json.dumps(commands,indent=2)+"\n")
    for command in commands:
        print("RUN", " ".join(command),flush=True)
        subprocess.run(command,check=True)
    for name in ("fsbl.elf","pmufw.elf","design_1_wrapper.bit","weights.bin","input.bin","output.bin","clock.txt"):
        with (DEPLOY/name).open("xb") as out, (ACCEPTED/name).open("rb") as src: shutil.copyfileobj(src,out)
    shutil.copy2(elf,DEPLOY/elf.name)
    for name in ("README.txt","summarize_results.py"):
        shutil.copy2(ROOT/name,DEPLOY/name)
    (DEPLOY/"boot.bif").write_text("the_ROM_image:\n{\n"
        " [bootloader, destination_cpu=a53-0] fsbl.elf\n"
        " [pmufw_image] pmufw.elf\n"
        " [destination_device=pl] design_1_wrapper.bit\n"
        " [destination_cpu=a53-0, exception_level=el-3] e07_image_accuracy.elf\n}\n")
    subprocess.run(["/opt/vivado/2025.1/Vivado/bin/bootgen","-arch","zynqmp","-image","boot.bif",
                    "-o","BOOT.BIN"],cwd=DEPLOY,check=True)
    if snapshot()!=before: raise RuntimeError("frozen inputs/source/deployment changed during build")
    identity={"scope":"PS-only real-image accuracy test of unchanged E07; no HLS/Vivado runs",
        "board_accuracy_status":"pending actual board run","frozen_files":before,
        "source_files":{str(p):digest(p) for p in sorted((ROOT/"src").glob("*"))},
        "compiler":gcc,"compiler_flags":flags,
        "bsp_libraries":{str(p):digest(p) for p in sorted((BSP/"lib").glob("*.a"))},
        "deployment_files":{p.name:{"bytes":p.stat().st_size,"sha256":digest(p)}
            for p in sorted(DEPLOY.iterdir()) if p.is_file()}}
    (DEPLOY/"identity.json").write_text(json.dumps(identity,indent=2)+"\n")
    with (DEPLOY/"manifest.csv").open("x",newline="") as f:
        w=csv.writer(f);w.writerow(["file","bytes","sha256"])
        for name,item in identity["deployment_files"].items(): w.writerow([name,item["bytes"],item["sha256"]])
    print(json.dumps(verify_deployment(DEPLOY),indent=2))


if __name__=="__main__": main()
