import json
DOC_ID = "4bc71039-2ff6-5204-a1d9-fd969588de98"
OUT = "data/extraction_results/" + DOC_ID + "_verified.json"
note = "D.C. Superior Court citing D.C. Court of Appeals - intra-DC court system. Rule 7.0 (D29): Domestic."
def mk(idx,verdict,name,raw,snip,year,conf,fu,fuc,op,xnote,dup=None):
    return {"citation_index":idx,"verification_verdict":verdict,"case_name":name,"raw_text":raw,"verbatim_snippet":snip,"cited_court":"District of Columbia Court of Appeals","case_number":None,"cited_year":year,"confidence":conf,"functional_use":fu,"functional_use_confidence":fuc,"opinion_type":op,"origin_country":"United States","origin_region":"Global North","origin_court":"District of Columbia Court of Appeals","sixfold_type":"Domestic","is_vertical_dialogue":False,"citation_pattern":"traditional","requires_manual_review":False,"manual_review_reason":None,"is_duplicate_of":dup,"verification_notes":xnote}
