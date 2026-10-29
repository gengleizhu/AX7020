"""Eight-worker DMA ABI, not wire-compatible with the single-core ABI."""
import struct
from codec import encode_batch,decode_result,verify_matches

def encode_superbatch(groups,targets,transaction_id):
    if len(groups)!=8 or len(targets)!=8:
        raise ValueError('Exactly eight groups and eight targets required')
    if not isinstance(transaction_id,int) or not 0<=transaction_id<=0xffffffff:
        raise ValueError('Transaction ID must be uint32')
    return struct.pack('<2I',0x38534344,transaction_id)+b''.join(
        encode_batch(words,target) for words,target in zip(groups,targets))

def decode_superresult(data,transaction_id):
    if len(data)!=168:
        raise ValueError('Expected 168-byte superbatch response')
    magic,tag=struct.unpack_from('<2I',data)
    if magic!=0x38524344 or tag!=transaction_id:
        raise ValueError('Wrong magic/transaction ID')
    results=[]
    for core in range(8):
        offset=8+20*core
        if struct.unpack_from('<I',data,offset)[0]!=core:
            raise ValueError('Wrong or duplicate core ID')
        results.append(decode_result(data[offset+4:offset+20]))
    return {'transaction_id':tag,'cores':results}

def verify_superresult(groups,targets,result):
    if len(groups)!=8 or len(targets)!=8 or len(result['cores'])!=8:
        raise ValueError('Eight groups required')
    for words,target,core in zip(groups,targets,result['cores']):
        core['verified_indices']=verify_matches(words,target,core['provisional_mask'])
    return result
