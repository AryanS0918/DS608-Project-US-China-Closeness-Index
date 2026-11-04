"""Build the edition-specific UNCTAD ICT-goods HS6 reference table from official PDFs."""
from __future__ import annotations
import argparse, re, subprocess
from pathlib import Path
import pandas as pd

YEARS=(2002,2007,2012,2017,2022)
CATEGORY_NAMES={
    "ICT01":"Computers and peripheral equipment",
    "ICT02":"Communication equipment",
    "ICT03":"Consumer electronic equipment",
    "ICT04":"Electronic components",
    "ICT05":"Miscellaneous",
}

def find_repository_root()->Path:
    for p in [Path(__file__).resolve().parent,*Path(__file__).resolve().parents]:
        if (p/"requirements.txt").exists(): return p
    raise FileNotFoundError("Repository root not found")

def pdf_to_text(pdf:Path)->str:
    result=subprocess.run(["pdftotext","-layout",str(pdf),"-"],check=True,capture_output=True,text=True)
    return result.stdout

def clean_line(line:str)->str:
    text=line.strip()
    if not text: return ""
    if text.startswith("ICT goods categories and composition") or text.startswith("Code"):
        return ""
    if text.startswith("Generation date:") or re.match(r"^Page \d+ of \d+",text):
        return ""
    if text.startswith("/Total ICT goods"):
        return ""
    return re.sub(r"\s+"," ",text)

def parse_pdf(text:str,year:int)->list[dict]:
    rows=[]; category=None; current=None
    def finish():
        nonlocal current
        if current:
            current["hs6_description"]=re.sub(r"\s+"," ",current["hs6_description"]).strip()
            rows.append(current); current=None
    for raw in text.splitlines():
        line=clean_line(raw)
        if not line: continue
        cat=re.match(r"^(ICT0[1-5])\s+(.+)$",line)
        if cat:
            finish(); category=cat.group(1); continue
        if line.startswith("ICT00"): finish(); continue
        item=re.match(r"^(\d{6})\s+(.+)$",line)
        if item:
            finish()
            if category is None: raise ValueError(f"HS code before category in HS {year}: {line}")
            current={"hs_revision":f"HS{year}","hs6_code":item.group(1),"hs6_description":item.group(2),
                     "ict_category_code":category,"ict_category_name":CATEGORY_NAMES[category]}
        elif current:
            current["hs6_description"] += " " + line
    finish()
    return rows

def build(source_dir:Path)->pd.DataFrame:
    rows=[]
    for year in YEARS:
        pdf=source_dir/f"DimHS{year}Products_Ict_Hierarchy.pdf"
        if not pdf.exists(): raise FileNotFoundError(pdf)
        rows.extend(parse_pdf(pdf_to_text(pdf),year))
    df=pd.DataFrame(rows)
    if df.empty: raise ValueError("No HS6 records parsed")
    if not df.hs6_code.str.fullmatch(r"\d{6}").all(): raise ValueError("Invalid HS6 code")
    dup=df.duplicated(["hs_revision","hs6_code"],keep=False)
    if dup.any(): raise ValueError("Duplicate edition-code rows:\n"+df.loc[dup].to_string(index=False))
    if set(df.ict_category_code) != set(CATEGORY_NAMES): raise ValueError("Missing ICT category")
    df["include_three_category"]=df.ict_category_code.isin(["ICT01","ICT02","ICT04"])
    df["include_baseline"]=df.ict_category_code.isin(["ICT01","ICT02","ICT04","ICT05"])
    df["include_broad_ict"]=True
    df["include_narrow_core"]=df.hs6_code.str[:4].isin(["8471","8517","8541","8542"])
    df["classification_source"]=df.hs_revision.map(lambda x:f"UNCTAD Dim{x}Products_Ict_Hierarchy.pdf")
    cols=["hs_revision","hs6_code","hs6_description","ict_category_code","ict_category_name",
          "include_baseline","include_three_category","include_broad_ict","include_narrow_core","classification_source"]
    return df[cols].sort_values(["hs_revision","ict_category_code","hs6_code"]).reset_index(drop=True)

def main():
    p=argparse.ArgumentParser(); p.add_argument("--source-dir",type=Path); p.add_argument("--output",type=Path)
    a=p.parse_args(); root=find_repository_root(); source=a.source_dir or root/"data"/"sources"/"unctad"/"ict_goods_classifications"; output=a.output or root/"data"/"reference"/"unctad_ict_goods_hs6.csv"
    df=build(source); output.parent.mkdir(parents=True,exist_ok=True); df.to_csv(output,index=False)
    print(df.groupby(["hs_revision","ict_category_code"]).size().unstack(fill_value=0).to_string())
    print(f"Saved {len(df):,} rows to {output}")
if __name__=="__main__": main()
