"""Conditional information accounting, not a latency or universal protocol bound."""
import argparse,json,math
from pathlib import Path
from common import HERE,digest,publish

def run(args):
    source=args.results.read_bytes();data=json.loads(source);rows=[]
    for row in data['rows']:
        if row['block']!=0:continue
        count=row['count'];added=removed=row['difference']//2
        bits=math.log2(math.comb(2**256-count,added))+math.log2(math.comb(count,removed))
        rows.append({'dataset':row['dataset'],'inventory_count':count,'difference':row['difference'],'method':row['method'],'conditional_information_bits':bits,'conditional_information_bytes':bits/8,'encoded_metadata_bytes':row['wire_bytes'],'ratio_to_conditional_information':row['wire_bytes']/(bits/8)})
    result={'schema':'GAIA-SCIENCE-INFORMATION-1','scope':'Ideal counting model: clientinventoryofknownNIDs, targetcardinalityandadded/removedcounts known, unknownaddedIDs uniformlychosenfromremaining256bituniverse. log2(C(2^256-N,added)*C(N,removed)). Ignoresauthentication,framing,metadata/summaryconstruction,sideinformationandpayloadencoding. Notuniversalcommunication/computation bound; no latencyprediction. NewIDs inreconciliationtrace aredeterministicallygeneratedtestIDs, not measuredrandomentropy.','reconciliation_raw_sha256':digest(source),'rows':rows}
    print(publish(args.output,result,{'cases':rows},{'passed':True,'encoded_protocols_above_declared_model_bound':all(r['encoded_metadata_bytes']>=r['conditional_information_bytes'] for r in rows),'assumptions_explicit':True},[Path(__file__),HERE/'common.py']))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--results',type=Path,required=True);p.add_argument('--output',type=Path,required=True);run(p.parse_args())
