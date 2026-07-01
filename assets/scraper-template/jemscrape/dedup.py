def collapse_stock(by_location, *, hub_group, ireland_branch):
    hub = max((by_location[b] for b in hub_group if b in by_location), default=0)
    uk_others = sum(
        max(v, 0) for b, v in by_location.items()
        if b not in hub_group and b != ireland_branch
    )
    uk = max(hub, 0) + uk_others
    ireland = max(by_location.get(ireland_branch, 0), 0)
    return {"total": uk + ireland, "uk": uk, "ireland": ireland}


def pick_price(prices, *, band_priority):
    if not prices:
        return None
    ranked = []
    for p in prices:
        band = p.get("band")
        rank = band_priority.index(band) if band in band_priority else len(band_priority)
        ranked.append((rank, p))
    ranked.sort(key=lambda rp: rp[0])
    return ranked[0][1]


def collapse_variants(records):
    groups = {}
    order = []
    for r in records:
        if r.product_id not in groups:
            groups[r.product_id] = []
            order.append(r.product_id)
        groups[r.product_id].append(r)

    out = []
    for pid in order:
        group = groups[pid]
        if len(group) == 1:
            out.append(group[0])
            continue
        best = min(group, key=lambda r: r.list_price if r.list_price is not None else float("inf"))
        setattr(best, "multi_variant", True)
        out.append(best)
    return out
