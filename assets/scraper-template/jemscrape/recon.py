import json
from dataclasses import dataclass, asdict

from .signals import detect_render, detect_auth, detect_antibot, analyze_shape
from .normalize import normalize
from .cache import atomic_write
from .errors import FetchError


@dataclass
class WarmupReport:
    source_site: str
    sampled: int
    fetched: int
    spa_count: int
    auth_count: int
    antibot_count: int
    fetch_errors: int
    parse_errors: int
    shape: dict
    per_url: list
    checklist: list

    def to_dict(self):
        return asdict(self)


def build_checklist(*, spa_count, auth_count, antibot_count, parse_errors, shape):
    items = []
    if spa_count:
        items.append("Site renderiza via JS (SPA): habilite o navegador/Playwright (Plano 3) — "
                     "o fetch HTTP puro não enxerga produto.")
    if auth_count:
        items.append("Login/paywall detectado: capture a sessão (storage_state) e logue no site antes do run.")
    if antibot_count:
        items.append("Anti-bot/geo detectado: configure proxy de país ou promova para VM (§5).")
    if parse_errors:
        items.append(f"{parse_errors} página(s) falharam ao parsear (parser/seletores incompletos) — "
                     "ajuste o parser antes do run.")
    cov = shape.get("coverage", {})
    if cov and cov.get("price", 1) < 0.5:
        items.append("Cobertura de preço < 50%: confirme se o preço exige login ou ajuste o parser.")
    if not items:
        items.append("Nenhum bloqueio detectado no HTTP puro — pronto para o review de sinal verde.")
    return items


def run_warmup(sample_urls, *, probe_fn, parse_fn, source_site,
               scraped_at, authorization_ref, raw_ref=""):
    per_url = []
    records = []
    spa_count = auth_count = antibot_count = fetch_errors = fetched = parse_errors = 0
    for url in sample_urls:
        entry = {"url": url}
        try:
            pr = probe_fn(url)
        except FetchError as exc:
            fetch_errors += 1
            entry["error"] = str(exc)
            per_url.append(entry)
            continue
        fetched += 1
        render = detect_render(pr.body)
        auth = detect_auth(pr)
        antibot = detect_antibot(pr)
        entry.update(status=pr.status, render=render, auth=auth, antibot=antibot)
        if render["mode"] == "spa":
            spa_count += 1
        if auth["auth_required"]:
            auth_count += 1
        if antibot["blocked"]:
            antibot_count += 1
        if render["mode"] == "server" and not auth["auth_required"] and not antibot["blocked"]:
            try:
                raw = parse_fn(pr.body, url)
                entry["parsed"] = bool(raw)
                if raw:
                    records.append(normalize(
                        raw, source_site=source_site, source_url=url,
                        scraped_at=scraped_at, authorization_ref=authorization_ref,
                        raw_ref=raw_ref))
            except Exception as exc:
                # A warm-up samples a site with an UNPROVEN parser: an
                # incomplete parse dict (parse_fn returns partial data, or
                # normalize()'s rec.validate() rejects it) is the expected
                # failure mode here, not a fatal error. Record it per-URL and
                # keep going so the rest of the sample's signal data survives.
                parse_errors += 1
                entry["parse_error"] = str(exc)
        per_url.append(entry)
    shape = analyze_shape(records)
    checklist = build_checklist(spa_count=spa_count, auth_count=auth_count,
                                antibot_count=antibot_count, parse_errors=parse_errors,
                                shape=shape)
    return WarmupReport(
        source_site=source_site, sampled=len(sample_urls), fetched=fetched,
        spa_count=spa_count, auth_count=auth_count, antibot_count=antibot_count,
        fetch_errors=fetch_errors, parse_errors=parse_errors, shape=shape,
        per_url=per_url, checklist=checklist)


def write_report(report, path):
    atomic_write(path, json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n")
