import sweep2, pickle, sys
sweep2.BANKS_SEL = sweep2.BANKS_HI
names=sys.argv[2].split('|'); sel=[m for m in sweep2.MACH if m[0] in names]
assert len(sel)==len(names)
r,e=sweep2.simulate(sel); pickle.dump((r,e),open('part_hi_%s.pkl'%sys.argv[1],'wb')); print('done',sys.argv[1])
