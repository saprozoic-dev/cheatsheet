import sweep2, pickle, sys
names=sys.argv[2].split('|'); sel=[m for m in sweep2.MACH if m[0] in names]
assert len(sel)==len(names),[m[0] for m in sel]
r,e=sweep2.simulate(sel); pickle.dump((r,e),open('part_%s.pkl'%sys.argv[1],'wb')); print('done',sys.argv[1])
