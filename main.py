import os, re, pandas as pd

IN_PATH  = "./sample_data/job_descriptions.xlsx"
OUT_FULL = "./job_descriptions_acceptance.xlsx"
OUT_APPLY_XLSX = "./job_descriptions_acceptance_apply_only.xlsx"
OUT_APPLY_CSV  = "./job_descriptions_acceptance_apply_only.csv"

def _rx(words): 
    return [re.compile(rf"\b{w}\b", re.I) for w in words]

RX = {
    "required": re.compile(r"\brequired|must|minimum\b", re.I),
    "senior_words": re.compile(r"\b(head|director|vp|lead)\b", re.I),
    "pm_words": _rx(["product manager","product management","roadmap","backlog","owner","prioriti[sz]e?"]),
    "agile": _rx(["agile","scrum","kanban","sprint"]),
    "xfn": _rx(["cross[- ]functional","stakeholder","exec","leadership","collaborat"]),
    "docs": _rx(["prd","product requirements","user stories","use cases","functional spec"]),
    "exp": _rx(["a/b testing","ab testing","experimentation","test.*learn"]),
    "kpi": _rx([r"\bkpi\b","metrics?","conversion","retention","growth"]),
    "domain": _rx(["e[- ]?commerce",r"\bsaas\b","platform",r"\bapi\b","marketplace","advertising","ad[- ]?tech","gaming","rewards?","loyalty","martech",r"\bcrm\b"]),
    "ai": _rx([r"\bai\b", r"\bllm\b", r"\bml\b", r"\brag\b","personalization"]),
    "tools": _rx([r"\bjira\b","productboard","tableau","google analytics",r"\bga4\b",r"\bsql\b","braze","iterable","salesforce marketing cloud","segment",r"\bmparticle\b","branch","kochava","appsflyer","airtable"]),
    "bilingual": _rx(["korean","korean[- ]english","korean/english",r"\bbilingual\b"]),
    "remote": re.compile(r"\bremote\b", re.I),
    "intern": re.compile(r"\bintern(ship)?\b", re.I),
    "fulltime": re.compile(r"\bfull[- ]?time\b", re.I),
    "far": _rx(["palo alto","mountain view","san jose","santa clara","sunnyvale","san francisco","oakland","sacramento","san diego","bay area"]),
    "salary_amt": re.compile(r"\$?\s*(\d{{2,3}})\s*[kK]\b")
}

def count_hits(text, pats): return sum(1 for p in pats if p.search(text or ""))
def ratio_cap(text, pats, cap): return min(count_hits(text, pats), cap) / cap if cap>0 else 0.0
def max_salary_k(text):
    nums=[]; 
    for m in RX["salary_amt"].finditer(text or ""):
        try: nums.append(int(m.group(1)))
        except: pass
    return max(nums) if nums else None
def in_required_line(text, key_rx):
    if not text: return False
    for line in re.split(r"[.\n;]", text):
        if RX["required"].search(line) and key_rx.search(line):
            return True
    return False

def acceptance_score(row):
    jd = str(row.get("description","")); loc = str(row.get("location","")); sal = str(row.get("salary",""))
    required_penalty = 0
    if in_required_line(jd, re.compile(r"\bsql\b", re.I)): required_penalty += 25
    if in_required_line(jd, re.compile(r"braze|iterable|salesforce marketing cloud", re.I)): required_penalty += 18
    required_score = max(0, 100 - required_penalty)
    senior_score = 100  # 10+ yrs
    resp_cov = ratio_cap(jd, RX["pm_words"]+RX["agile"]+RX["xfn"]+RX["docs"]+RX["exp"]+RX["kpi"], cap=8)
    dom_cov  = ratio_cap(jd, RX["domain"], cap=6)
    tool_cov = ratio_cap(jd, RX["tools"], cap=8)
    base = 0.35*required_score + 0.10*senior_score + 0.20*(100*resp_cov) + 0.20*(100*dom_cov) + 0.10*(100*tool_cov) + 0.05*100
    if any(p.search(jd) for p in RX["bilingual"]): base += 8
    if any(p.search(jd) for p in RX["ai"]): base += 4
    sal_k = max_salary_k(jd + " " + sal); remote = bool(RX["remote"].search(jd) or RX["remote"].search(loc))
    far_on_site = (not remote) and any(p.search(jd + " " + loc) for p in RX["far"])
    if sal_k is not None and sal_k <= 120 and far_on_site: base *= 0.70
    if RX["intern"].search(jd) and not RX["fulltime"].search(jd): base = 0
    return int(round(max(0, min(92, base))))

def pick_sentences(text, patterns, n=2):
    sents = re.split(r"(?<=[.!?])\s+|\n+", text or "")
    hits = []
    for s in sents:
        if any(re.search(p, s, re.I) for p in patterns):
            ss = s.strip()
            if 20 <= len(ss) <= 180 and ss not in hits:
                hits.append(ss)
        if len(hits) >= n: break
    return hits

def make_cv(row, s):
    if s < 70: return "", "", ""
    jd = str(row.get("description","")); title = str(row.get("title","")).strip() or "Product Manager"; company = str(row.get("company","")).strip() or "the company"
    wants_ai = any(re.search(p, jd, re.I) for p in [r"\bai\b", r"\bllm\b", r"\bml\b", r"\brag\b","personalization"])
    wants_kr = any(re.search(p, jd, re.I) for p in ["korean","korean[- ]english","korean/english",r"\bbilingual\b"])
    summary = (
        f"Product leader with 10+ years in e-commerce/SaaS platforms, API products, and cross-functional delivery. "
        f"Owned roadmaps and PRDs, scaled high-transaction launches, and drove KPI-based iteration with Engineering/Design/Go-to-Market. "
        + ("Fluent KR/EN. " if wants_kr else "") + ("Applied AI for automation/workflows; comfortable partnering with data/ML teams. " if wants_ai else "")
        + f"Ready to drive outcomes as {{title}} at {{company}}."
    )
    skills = ["Product strategy & roadmaps","API/platform products","Agile (Scrum/Kanban)","PRDs, user stories, acceptance criteria","Experimentation & KPI tracking","Stakeholder & cross-functional leadership","JIRA, Confluence, Figma, Tableau, Google Analytics","E-commerce & marketplace operations"]
    if wants_ai: skills.insert(2, "LLM/automation use-cases (prompting, workflow integration)")
    if wants_kr: skills.append("Bilingual: Korean/English")
    jd_themes = pick_sentences(jd, [r"roadmap|launch|experimen|kpi|api|platform|e[- ]?commerce|saas|ad[- ]?tech|gaming|loyalty|crm|personalization"], n=2)
    bullets = jd_themes + [
        "Led API product strategy and platform roadmap; delivered features across Eng/QA/Design with clear PRDs and tight sprint cadences.",
        "Built an open API app store ecosystem, reducing customization costs by 90% and accelerating integrations for partners.",
        "Stabilized critical API servers (CPU 90% → 60%) and supported high-transaction launches for Nike, YG Entertainment, and SM Entertainment.",
        "Partnered with YouTube Shopping on global expansion initiatives.",
        "Scaled global e-commerce operations (Amazon/eBay integrations) and achieved 473% YoY revenue growth for Kmall24.",
    ]
    seen=set(); out=[]
    for b in bullets:
        b = re.sub(r"\s+"," ", str(b)).strip("• ").strip()
        if b and b.lower() not in seen:
            seen.add(b.lower()); out.append("• " + b)
        if len(out)>=6: break
    return summary, "; ".join(skills[:10]), "\n".join(out)

def main():
    if not os.path.exists(IN_PATH):
        # Fallback to CSV sample
        IN_CSV = "./sample_data/job_descriptions.csv"
        import csv
        if not os.path.exists(IN_CSV):
            raise FileNotFoundError("Provide sample_data/job_descriptions.xlsx or sample_data/job_descriptions.csv")
        df = pd.read_csv(IN_CSV)
    else:
        df = pd.read_excel(IN_PATH)
    for col in ["url","title","company","description","location","salary"]:
        if col not in df.columns: df[col] = ""
    rows=[]
    for _, r in df.iterrows():
        s=acceptance_score(r)
        cv_sum, cv_skill, cv_exp = make_cv(r, s)
        decision = "Apply (Priority)" if s >= 80 else ("Apply" if s >= 70 else "Skip")
        out=dict(r); out["accept_score"]=s; out["decision"]=decision
        out["cv_summary"]=cv_sum; out["cv_skills"]=cv_skill; out["cv_experience_bullets"]=cv_exp
        rows.append(out)
    df_out=pd.DataFrame(rows).sort_values("accept_score", ascending=False)
    df_out.to_excel(OUT_FULL, index=False)
    df_apply=df_out[df_out["accept_score"]>=70].copy()
    df_apply.to_excel(OUT_APPLY_XLSX, index=False)
    df_apply.to_csv(OUT_APPLY_CSV, index=False)
    print("Wrote:", OUT_FULL, OUT_APPLY_XLSX, OUT_APPLY_CSV)

if __name__ == "__main__":
    main()
