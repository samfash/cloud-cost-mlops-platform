/* Elector: line protocol in, winning trial_id out */

nmin = 100; nmax = 800; reqfeat = 'sqrt'; reqseed = 42
neednull = 1; pvmax = 4.5; excl.0 = 0; nt = 0

do forever
  parse pull line
  if line = 'END' then leave
  if line = '' then iterate
  parse var line key rest
  select
    when key = 'N_ESTIMATORS_MIN' then nmin = rest + 0
    when key = 'N_ESTIMATORS_MAX' then nmax = rest + 0
    when key = 'REQUIRED_MAX_FEATURES' then reqfeat = rest
    when key = 'REQUIRED_RANDOM_STATE' then reqseed = rest + 0
    when key = 'REQUIRE_UNLIMITED_DEPTH' then neednull = rest + 0
    when key = 'PRED_VAR_MAX' then pvmax = rest + 0
    when key = 'EXCLUDE' then do
      excl.0 = excl.0 + 1
      ei = excl.0
      excl.ei = translate(rest)
    end
    when key = 'TRIAL' then do
      nt = nt + 1
      t.id.nt = ''; t.nest.nt = 0; t.depth.nt = '_'
      t.feat.nt = ''; t.seed.nt = 0
      t.rmse.nt = 0; t.mae.nt = 0; t.r2.nt = 0
      t.pv.nt = 0; t.fp.nt = ''
    end
    when key = 'ID' then t.id.nt = rest
    when key = 'N_ESTIMATORS' then t.nest.nt = rest + 0
    when key = 'MAX_DEPTH' then t.depth.nt = rest
    when key = 'MAX_FEATURES' then t.feat.nt = rest
    when key = 'RANDOM_STATE' then t.seed.nt = rest + 0
    when key = 'RMSE' then t.rmse.nt = rest + 0
    when key = 'MAE' then t.mae.nt = rest + 0
    when key = 'R2' then t.r2.nt = rest + 0
    when key = 'PRED_VAR' then t.pv.nt = rest + 0
    when key = 'FINGERPRINT' then t.fp.nt = translate(rest)
    otherwise nop
  end
end

ns = 0
do i = 1 to nt
  if t.nest.i < nmin then iterate
  if t.nest.i > nmax then iterate
  if t.feat.i \= reqfeat then iterate
  if t.seed.i \= reqseed then iterate
  if neednull = 1 & t.depth.i \= '_' then iterate
  if t.pv.i > pvmax then iterate
  denied = 0
  do e = 1 to excl.0
    if t.fp.i = excl.e then denied = 1
  end
  if denied = 1 then iterate
  ns = ns + 1
  sx.ns = i
end
if ns = 0 then do; say 'NONE'; exit 1; end

do pass = 1 to 3
  do j = 1 to ns
    i = sx.j
    if pass = 1 then ch.j = t.rmse.i
    if pass = 2 then ch.j = t.mae.i
    if pass = 3 then ch.j = t.r2.i
    ord.j = j
  end
  if pass = 3 then higher = 1
  else higher = 0
  do a = 1 to ns - 1
    do b = a + 1 to ns
      ia = ord.a
      ib = ord.b
      va = ch.ia
      vb = ch.ib
      swap = 0
      if higher = 1 then do
        if va < vb then swap = 1
      end
      else do
        if va > vb then swap = 1
      end
      if swap = 1 then do
        tmp = ord.a
        ord.a = ord.b
        ord.b = tmp
      end
    end
  end
  p = 1
  do while p <= ns
    q = p
    ip = ord.p
    v0 = ch.ip
    do while q <= ns
      iq = ord.q
      if ch.iq \= v0 then leave
      q = q + 1
    end
    avg = (p + q - 1) / 2
    do r = p to q - 1
      oj = ord.r
      ranks.oj = avg
    end
    p = q
  end
  do j = 1 to ns
    pts = ns - ranks.j
    if pass = 1 then br.j = pts
    if pass = 2 then ba.j = pts
    if pass = 3 then b2.j = pts
  end
end

do j = 1 to ns
  borda.j = br.j + ba.j + b2.j
  cope.j = 0
end

do a = 1 to ns - 1
  do b = a + 1 to ns
    ia = sx.a
    ib = sx.b
    wa = 0
    wb = 0
    if t.rmse.ia < t.rmse.ib then wa = wa + 1
    else if t.rmse.ia > t.rmse.ib then wb = wb + 1
    if t.mae.ia < t.mae.ib then wa = wa + 1
    else if t.mae.ia > t.mae.ib then wb = wb + 1
    if t.r2.ia > t.r2.ib then wa = wa + 1
    else if t.r2.ia < t.r2.ib then wb = wb + 1
    if wa > wb then cope.a = cope.a + 1
    else if wb > wa then cope.b = cope.b + 1
  end
end

best = 1
do j = 2 to ns
  replace = 0
  if borda.j \= borda.best then do
    if borda.j > borda.best then replace = 1
  end
  else if cope.j \= cope.best then do
    if cope.j > cope.best then replace = 1
  end
  else do
    ia = sx.j
    ib = sx.best
    if t.pv.ia \= t.pv.ib then do
      if t.pv.ia < t.pv.ib then replace = 1
    end
    else if t.fp.ia \= t.fp.ib then do
      if t.fp.ia < t.fp.ib then replace = 1
    end
    else do
      if t.id.ia < t.id.ib then replace = 1
    end
  end
  if replace = 1 then best = j
end

wi = sx.best
say t.id.wi
exit 0
