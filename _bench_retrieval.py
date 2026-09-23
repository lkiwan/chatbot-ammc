import time, sys
sys.path.insert(0, '.')
from chat import load_store, retrieve, build_messages

t0 = time.time()
store = load_store()
t1 = time.time()
hits = retrieve(store, 'Quelle est la strategie de developpement ?', k=10)
t2 = time.time()
msgs = build_messages('Quelle est la strategie ?', hits, [])
ctx_chars = sum(len(m['content']) for m in msgs)
print(f'load_store:  {t1-t0:.2f}s')
print(f'retrieve:    {t2-t1:.2f}s')
print(f'hits:        {len(hits)}')
print(f'context:     {ctx_chars} chars  (~{ctx_chars//4} tokens)')
if hits:
    print(f'first hit:   {hits[0]["report"]}  yr={hits[0]["year"]}  p={hits[0]["page"]}')
