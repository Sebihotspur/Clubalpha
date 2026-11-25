const app = document.querySelector("#app");

const esc = (value) =>
  String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

const pct = (value) => `${(Number(value) * 100).toFixed(1)}%`;
const dec = (value, places = 2) => Number(value).toFixed(places);
const signed = (value, places = 2) => `${Number(value) >= 0 ? "+" : ""}${Number(value).toFixed(places)}`;
const dateTime = (value) =>
  new Intl.DateTimeFormat("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZone: "America/New_York",
    timeZoneName: "short",
  }).format(new Date(value));
const dateOnly = (value) =>
  new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(value));
const kickoffTime = (value) => new Intl.DateTimeFormat("en-US", {
  hour: "numeric", minute: "2-digit", timeZone: "America/New_York", timeZoneName: "short",
}).format(new Date(value));

function routeName() {
  const query = new URLSearchParams(location.search).get("view");
  if (query) return query;
  return location.pathname.split("/").filter(Boolean)[0] || "overview";
}

function activateNav(route) {
  document.querySelectorAll("[data-route]").forEach((link) => {
    link.classList.toggle("active", link.dataset.route === route);
  });
}

function pageHead(kicker, title, copy = "") {
  return `<header class="page-head clean-head">
    <p class="eyebrow">${esc(kicker)}</p><h1>${esc(title)}</h1>
    ${copy ? `<p>${esc(copy)}</p>` : ""}
  </header>`;
}

const totalLabel = (value) => ({ over_2_5: "Over 2.5", under_2_5: "Under 2.5" }[value]);
const money = (value) => new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);

function sideLabel(row, value) {
  return ({ home_win: row.home_team, away_win: row.away_team, draw: "Draw" }[value]) || "Pass";
}

function matchupLink(row) {
  return `/matchups/?home=${encodeURIComponent(row.home_team)}&amp;away=${encodeURIComponent(row.away_team)}`;
}

function slateSummary(slate) {
  const pending = slate.fixtures.filter((row) => !row.score);
  if (!pending.length) return `${slate.settled}/${slate.fixtures.length} results in the ledger.`;
  const sides = pending.filter((row) => row.side_call !== "pass").length;
  const totals = pending.filter((row) => totalLabel(row.total_call)).length;
  return `${pending.length} pending · ${sides || "No"} 1X2 ${sides === 1 ? "pick" : "picks"} · ${totals || "no"} O/U ${totals === 1 ? "pick" : "picks"}`;
}

function paperPosition(position, slate) {
  const status = position.settled ? (position.won ? "Won" : "Lost") : "Pending";
  const market = totalLabel(position.outcome);
  const price = position.captured_best_ask == null ? "No captured ask" : `${Math.round(position.captured_best_ask * 100)}¢ entry`;
  const match = !position.settled && slate?.fixtures.find((row) =>
    !row.score && `${row.home_team} vs ${row.away_team}` === position.fixture &&
    row.kickoff_utc === position.kickoff_utc
  );
  const projectedTotal = match?.predicted_xg?.total;
  const isHighest = Number.isFinite(projectedTotal) && slate.fixtures.every((row) =>
    (row.predicted_xg?.total ?? -Infinity) <= projectedTotal
  );
  const context = Number.isFinite(projectedTotal)
    ? `${dec(projectedTotal)} projected total xG${isHighest ? ", the highest on this slate" : ""}.${match.side_call === "pass" ? " No winner pick." : ""}`
    : "";
  return `<article class="paper-card">
    <div>
      <div class="paper-tag"><span>Paper position</span><span class="paper-state">${status}</span></div>
      <h3>${esc(position.fixture)}</h3>
      <p>${esc(market ? `${market} goals` : position.outcome.replaceAll("_", " "))} · ${esc(price)}${position.settled && position.score ? ` · Final ${esc(position.score)}` : ""}</p>
      ${context ? `<p class="paper-context">${esc(context)} <a href="${matchupLink(match)}">Matchup details</a></p>` : ""}
    </div>
    <div class="paper-size"><strong>${position.risk_reference == null ? `${dec(position.official_stake_units)}u` : money(position.risk_reference)}</strong>
    <small>${position.risk_reference == null ? "Paper stake" : "Simulated risk at entry"}</small></div>
  </article>`;
}

function overview(data) {
  const latest = data.premier_league[0];
  const uclSettled = data.ucl.fixtures.filter((row) => row.status === "final").length;
  const pending = data.paper.positions.find((position) => !position.settled);
  return `<section class="clean-hero${latest ? " clean-hero-with-slate" : ""}">
    <div>
      <p class="eyebrow">Premier League · Champions League</p>
      <h1>Football intelligence,<br><span>earned in public.</span></h1>
      <p class="hero-intro">Upcoming forecasts, final scores, and a transparent paper record.</p>
    </div>
    ${latest ? `<aside class="week-brief" aria-label="Premier League at a glance">
      <span>Premier League at a glance</span>
      <strong>Matchweek ${esc(latest.round)}</strong>
      <p>${esc(slateSummary(latest))}</p>
      <a href="/predictions/">View the slate</a>
    </aside>` : ""}
  </section>
  ${pending ? paperPosition(pending) : ""}
  <section class="home-links" aria-label="Explore Clubalpha">
    <a href="/predictions/"><span>Premier League</span><strong>Matchweek ${esc(latest?.round ?? "—")}</strong><small>Fixtures and forecasts</small></a>
    <a href="/ucl/"><span>Champions League</span><strong>Matchday ${esc(data.ucl.matchday)}</strong><small>${uclSettled}/${data.ucl.fixtures.length} final scores</small></a>
    <a href="/matchups/"><span>Matchups</span><strong>Compare two teams</strong><small>Venue, probabilities and playing styles</small></a>
    <a href="/ledger/"><span>Ledger</span><strong>Track the record</strong><small>Results and simulated performance</small></a>
  </section>`;
}

function fixtureList(slate) {
  const mixed = slate.fixtures.some((row) => !row.score && row.final_forecast) && slate.provisional;
  return `<div class="clean-list">
    <div class="fixture-columns" aria-hidden="true"><span>Fixture</span><span>1X2</span><span>Goals</span><span>Result</span></div>
    <ul class="fixture-list">
    ${slate.fixtures.map((row) => {
      const side = sideLabel(row, row.side_call);
      const total = totalLabel(row.total_call) || "Pass";
      const probability = row.total_call === "over_2_5" ? row.over_probability : 1 - row.over_probability;
      return `<li>
        <div class="fixture-name"><a href="${matchupLink(row)}">${esc(row.home_team)} <span>vs</span> ${esc(row.away_team)}</a>
        <small>${esc(dateTime(row.kickoff_utc))}${mixed && !row.score && !row.final_forecast ? " · Provisional" : ""}</small></div>
        <div class="fixture-call"><small>1X2</small><strong class="${side === "Pass" ? "quiet" : ""}">${esc(side)}</strong></div>
        <div class="fixture-call"><small>Goals</small><strong class="${total === "Pass" ? "quiet" : "green"}">${esc(total)}${total === "Pass" ? "" : ` · ${pct(probability)}`}</strong></div>
        <div class="fixture-score"><small>Result</small><strong>${esc(row.score ?? "—")}</strong></div>
      </li>`;
    }).join("")}
  </ul></div>`;
}

function predictions(data) {
  const [latest, previous] = data.premier_league;
  if (!latest) return pageHead("Premier League", "Predictions", "No frozen slate available.");
  const pending = data.paper.positions.filter((position) => !position.settled);
  const snapshot = new Date(latest.updated_at).toLocaleDateString("en-US", {
    month: "short", day: "numeric", timeZone: "America/New_York",
  });
  return `${pageHead("Premier League", `Matchweek ${latest.round}`,
    `${latest.provisional ? "Provisional forecasts" : "Frozen forecasts"} · Snapshot ${snapshot}.`)}
  ${pending.map((position) => paperPosition(position, latest)).join("")}
  <section class="clean-section"><div class="clean-section-head"><h2>Fixtures</h2><span>${latest.settled}/${latest.fixtures.length} final</span></div>
  ${fixtureList(latest)}</section>
  ${previous ? `<details class="clean-fold">
    <summary>Matchweek ${previous.round} results <span>${previous.settled}/${previous.fixtures.length} final</span></summary>
    ${previous.settled ? `<p class="fold-note">Model directions: 1X2 ${previous.leader_hits}/${previous.settled} · O/U 2.5 ${previous.total_direction_hits}/${previous.settled}</p>` : ""}
    ${fixtureList(previous)}
  </details>` : ""}`;
}

function ucl(data) {
  const cup = data.ucl;
  const settled = cup.fixtures.filter((row) => row.status === "final").length;
  const archive = cup.last_forecast_review;
  const review = archive.settlement;
  const byDay = new Map();
  for (const row of cup.fixtures) {
    const day = new Date(row.kickoff_utc).toLocaleDateString("en-US", {
      weekday: "long", month: "short", day: "numeric", timeZone: "America/New_York",
    });
    if (!byDay.has(day)) byDay.set(day, []);
    byDay.get(day).push(row);
  }
  return `${pageHead("Champions League", `Matchday ${cup.matchday}`, `${settled}/${cup.fixtures.length} final · Scores checked ${dateTime(cup.captured_at_utc)}.`)}
    ${!review || Number(archive.matchday) !== Number(cup.matchday) ? `<p class="clean-note">Results only. No frozen forecast is scored for this matchday.</p>` : ""}
    ${[...byDay].map(([day, rows]) => `<section class="clean-section cup-day">
      <div class="clean-section-head"><h2>${esc(day)}</h2></div>
      <ul class="scoreboard clean-list">${rows.map((row) => `<li>
        <div class="fixture-name"><strong>${esc(row.home_team)} <span>vs</span> ${esc(row.away_team)}</strong>
        <small>${esc(kickoffTime(row.kickoff_utc))}</small></div>
        <div class="cup-result">${row.status === "final" ? `<strong>${esc(String(row.score).replace(/\s*-\s*/g, "–"))}</strong>` :
          `<small>${row.status === "in_progress" ? "In progress" : row.status === "postponed" ? "Postponed" : "Scheduled"}</small>`}</div>
      </li>`).join("")}</ul>
    </section>`).join("")}
    <p class="clean-note"><a href="${esc(cup.source_url)}">FotMob scores</a></p>
    ${review ? `<details class="clean-fold"><summary>Matchday ${esc(archive.matchday)} forecast record</summary>
      <div class="fold-body">
        <p>1X2 leaders: <strong>${review.raw_probability_leader.hits}/${review.raw_probability_leader.settled}</strong></p>
        <p>O/U 2.5 directions: <strong>${review.raw_over_under_2_5.hits}/${review.raw_over_under_2_5.settled}</strong></p>
      </div>
    </details>` : ""}`;
}

const ledgerMarkets = [
  ["one_x_two", "1X2", "side"],
  ["over_under_2_5", "O/U 2.5", "total"],
];

const hitMiss = (hits, misses) =>
  `${hits} ${hits === 1 ? "hit" : "hits"} · ${misses} ${misses === 1 ? "miss" : "misses"}`;

function forecastRecord(record) {
  if (!record) return "";
  const archive = record.official_archive_1x2;
  return `<section class="clean-section forecast-record" aria-labelledby="forecast-record-title">
    <div class="clean-section-head"><h2 id="forecast-record-title">Published call record</h2>
      <span>${record.from_matchweek ? `MW${esc(record.from_matchweek)} onward` : "Premier League"}</span></div>
    <div class="record-grid">${ledgerMarkets.map(([key, label]) => {
      const market = record.markets[key];
      return `<div class="record-metric"><h3>${label}</h3>
        <strong>${market.hit_rate == null ? "—" : pct(market.hit_rate)}</strong>
        <p>${market.settled ? hitMiss(market.hits, market.misses) : "No settled calls"}</p>
      </div>`;
    }).join("")}</div>
    ${archive.settled ? `<p class="clean-note">Earlier official 1X2 archive: ${pct(archive.hit_rate)} · ${hitMiss(archive.hits, archive.misses)}.</p>` : ""}
  </section>`;
}

function matchweekFold(week) {
  const noPublishedCalls = week.settled && ledgerMarkets.every(([key]) => !week.markets[key].settled);
  const basis = ({
    selective_calls: noPublishedCalls ? "No settled calls" : "Published calls",
    official_archive: "Official 1X2 archive · Model totals",
    full_slate: "Full-slate model record",
  })[week.basis];
  return `<details class="clean-fold ledger-week"><summary>
    <span class="week-row">
      <span class="week-name"><strong>Matchweek ${esc(week.matchweek)}</strong>
        <small>${week.settled}/${week.fixtures} final${basis ? ` · ${esc(basis)}` : ""}</small></span>
      ${ledgerMarkets.map(([key, label, direction]) => {
        const market = week.markets[key];
        const modelOnly = !market.settled && week.settled && week.model_directions;
        const rate = market.settled ? pct(market.hit_rate)
          : modelOnly ? pct(week.model_directions[direction] / week.settled)
            : week.settled ? "No calls" : "Pending";
        const sample = market.settled ? `${market.hits}/${market.settled}`
          : modelOnly ? `${week.model_directions[direction]}/${week.settled}` : "";
        return `<span class="week-rate"><small>${label}${modelOnly ? " · model" : ""}</small><strong>${rate}${sample ? ` <em>${sample}</em>` : ""}</strong></span>`;
      }).join("")}
    </span>
  </summary>
    <div class="fold-body">${ledgerMarkets.map(([key]) => {
      const market = week.markets[key];
      return `<p>${esc(market.label)} <strong>
        ${market.settled ? hitMiss(market.hits, market.misses) : week.settled ? "No calls" : "Awaiting results"}
      </strong></p>`;
    }).join("")}</div>
    ${week.model_directions ? `<p class="fold-note">Model only: 1X2 ${hitMiss(week.model_directions.side, week.settled - week.model_directions.side)}; O/U 2.5 ${hitMiss(week.model_directions.total, week.settled - week.model_directions.total)}.</p>` : ""}
  </details>`;
}

function ledger(data) {
  const book = data.paper.positions;
  const settled = book.filter((row) => row.settled);
  const pnl = settled.reduce((sum, row) => sum + (row.official_gross_pnl_units ?? 0), 0);
  return `${pageHead("Paper only", "Ledger", "Frozen forecasts, match results, and simulated positions.")}
    ${forecastRecord(data.forecast_record)}
    <section class="clean-section"><div class="clean-section-head"><h2>Matchweek hit rates</h2></div>
      ${data.matchweeks.map(matchweekFold).join("")}
    </section>
    <section class="clean-section">
      <div class="clean-section-head"><h2>Paper positions</h2><span>${book.length - settled.length} pending · ${settled.length} settled</span></div>
      ${book.length ? book.map((position) => paperPosition(position)).join("") : '<p class="clean-note">No paper positions recorded.</p>'}
      <div class="ledger-totals">
        <p><span>Settled paper P&amp;L</span><strong>${pnl > 0 ? "+" : ""}${dec(pnl)}u</strong></p>
        ${data.paper.standardized_bankroll == null ? "" : `<p><span>Separate $100k simulation</span><strong>${money(data.paper.standardized_bankroll)}</strong></p>`}
      </div>
      ${data.paper.standardized_bankroll == null ? "" : '<p class="clean-note">The $100k simulation is a separate benchmark. Paper positions do not change its balance.</p>'}
    </section>`;
}

function signalMeter(value, kind) {
  const bounded = Math.max(-1.5, Math.min(1.5, Number(value) || 0));
  const width = (Math.abs(bounded) / 1.5) * 50;
  const direction = bounded >= 0 ? "positive" : "negative";
  return `<div class="signal-meter ${esc(kind)}"><span class="signal-fill ${direction}" style="width:${width.toFixed(1)}%"></span></div><span class="signal-value">${signed(value)}</span>`;
}

function xiExecutionEdge(channel, attacker, defender) {
  const attack = attacker.projected_xi;
  const defence = Number(defender.projected_xi.defensive_prevention) || 0;
  if (channel.key === "box_pressure") {
    return ((Number(attack.chance_creation) || 0) + (Number(attack.scoring_threat) || 0)) / 2 - defence;
  }
  if (channel.key === "wide_delivery") {
    return (Number(attack.chance_creation) || 0) - defence;
  }
  if (channel.key === "high_press") {
    return (Number(attack.defensive_prevention) || 0) - (Number(defender.projected_xi.chance_creation) || 0);
  }
  return (Number(attack.scoring_threat) || 0) - defence;
}

function matchupVerdict(value, boundaries) {
  if (value >= boundaries.strong_route) return ["Strong route", "strong"];
  if (value >= boundaries.leans_favorable) return ["Leans favorable", "favorable"];
  if (value <= boundaries.likely_resisted) return ["Likely resisted", "resisted"];
  return ["No clear edge", "neutral"];
}

function matchupRows(snapshot, attacker, defender) {
  const boundaries = snapshot.method.decision_boundaries;
  return snapshot.channels.map((channel) => {
    const route = Number(attacker.route_expression[channel.key]) || 0;
    const exposure = Number(defender.opponent_exposure[channel.key]) || 0;
    const xi = xiExecutionEdge(channel, attacker, defender);
    const routeFit = (route + exposure) / 2;
    const score = 0.70 * routeFit + 0.30 * xi;
    const [label, tone] = matchupVerdict(score, boundaries);
    return { channel, route, exposure, xi, score, label, tone };
  });
}

function renderMatchup(snapshot, roundRobin, slate) {
  const attackerName = document.querySelector("#matchup-attacker")?.value;
  const defenderName = document.querySelector("#matchup-defender")?.value;
  const attacker = snapshot.teams.find((team) => team.team === attackerName);
  const defender = snapshot.teams.find((team) => team.team === defenderName);
  if (!attacker || !defender) return;

  document.querySelector("#attacker-name").textContent = attacker.team;
  const attackerFlags = attacker.quality_flags.length ? " · evidence flagged" : "";
  const defenderFlags = defender.quality_flags.length ? " · evidence flagged" : "";
  document.querySelector("#attacker-type").textContent = `${attacker.archetype}${attackerFlags}`;
  document.querySelector("#defender-name").textContent = defender.team;
  document.querySelector("#defender-type").textContent = `${defender.archetype}${defenderFlags}`;

  const rows = matchupRows(snapshot, attacker, defender);
  const pair = (fixture) => fixture.home_team === attacker.team && fixture.away_team === defender.team;
  const scheduled = slate?.fixtures.find(pair);
  const probability = scheduled || roundRobin.fixtures.find(pair);
  document.querySelector("#matchup-probability-source").textContent = scheduled
    ? `Matchweek ${slate.round} · ${scheduled.final_forecast ? "Frozen fixture forecast" : "Provisional fixture forecast"} · ${dateTime(scheduled.frozen_at)}`
    : probability ? `Round-robin benchmark · ${dateOnly(roundRobin.meta.as_of)} · Not a fixture forecast` : "";
  if (probability) {
    document.querySelector("#round-robin-probability").innerHTML = `
      <div class="outcome-probability home"><span>${esc(attacker.team)} win</span><strong>${pct(probability.probabilities.home_win)}</strong></div>
      <div class="outcome-probability draw"><span>Draw</span><strong>${pct(probability.probabilities.draw)}</strong></div>
      <div class="outcome-probability away"><span>${esc(defender.team)} win</span><strong>${pct(probability.probabilities.away_win)}</strong></div>
      <div class="matchup-xg"><span>Projected xG</span><strong>${dec(probability.predicted_xg.home)}–${dec(probability.predicted_xg.away)}</strong><small>${dec(probability.predicted_xg.total)} total</small></div>`;
  } else {
    document.querySelector("#round-robin-probability").innerHTML = `<div class="matchup-empty">Select two different clubs to load a fixture probability.</div>`;
  }
  document.querySelector("#matchup-route-rows").innerHTML = rows
    .map(
      (row) => `<div class="route-row">
        <div class="route-name"><strong>${esc(row.channel.label)}</strong><span>${esc(row.channel.evidence_tier)} · ${row.channel.exposure_type === "style_invitation" ? "style invitation" : "defensive exposure"}</span></div>
        <div class="route-signal" data-label="Attack expression">${signalMeter(row.route, "attack")}</div>
        <div class="route-signal" data-label="Opponent exposure">${signalMeter(row.exposure, "exposure")}</div>
        <div class="route-signal" data-label="XI execution edge">${signalMeter(row.xi, "xi")}</div>
        <div class="route-verdict ${row.tone}">${esc(row.label)}</div>
      </div>`,
    )
    .join("");
  const best = rows.slice().sort((a, b) => b.score - a.score)[0];
  document.querySelector("#matchup-best-route").innerHTML = `<span>Clearest current route</span><strong>${esc(best.channel.label)}</strong><small>${signed(best.score)} challenger signal</small>`;
}

function bindMatchups(snapshot, roundRobin, slate) {
  const attacker = document.querySelector("#matchup-attacker");
  const defender = document.querySelector("#matchup-defender");
  if (!attacker || !defender) return;
  const render = () => renderMatchup(snapshot, roundRobin, slate);
  attacker.addEventListener("change", render);
  defender.addEventListener("change", render);
  document.querySelector("#matchup-swap").addEventListener("click", () => {
    const previous = attacker.value;
    attacker.value = defender.value;
    defender.value = previous;
    render();
  });
  render();
}

function archetypeCards(snapshot) {
  const groups = new Map();
  snapshot.teams.forEach((team) => {
    if (!groups.has(team.archetype)) groups.set(team.archetype, []);
    groups.get(team.archetype).push(team.team);
  });
  return [...groups.entries()]
    .map(
      ([archetype, teams]) => `<article class="archetype-card"><span class="panel-label">${String(teams.length).padStart(2, "0")} clubs</span><h3>${esc(archetype)}</h3><p>${teams.map(esc).join(" · ")}</p></article>`,
    )
    .join("");
}

function roundRobinTable(roundRobin) {
  return roundRobin.league_table
    .map(
      (team) => `<tr>
        <td>${team.rank}</td>
        <td class="fixture-cell"><strong>${esc(team.team)}</strong><span>Average W/D/L · ${pct(team.average_probabilities.win)} / ${pct(team.average_probabilities.draw)} / ${pct(team.average_probabilities.loss)}</span></td>
        <td>${dec(team.expected_wins)}</td>
        <td>${dec(team.expected_draws)}</td>
        <td>${dec(team.expected_losses)}</td>
        <td class="prob-main">${dec(team.expected_points)}</td>
        <td>${team.expected_goal_difference >= 0 ? "+" : ""}${dec(team.expected_goal_difference)}</td>
      </tr>`,
    )
    .join("");
}

function matchups(data) {
  const snapshot = data.style_matchup;
  const options = snapshot.teams.map((team) => `<option value="${esc(team.team)}">${esc(team.team)}</option>`).join("");
  return `<section class="page-head"><p class="eyebrow">Premier League matchup explorer</p><h1>Matchup probabilities</h1><p>Choose the home and away teams to compare outcome probabilities, expected goals, and tactical routes. Scheduled pairs show the latest saved fixture forecast; other pairs show the dated round-robin benchmark.</p></section>
    <section class="matchup-lab">
      <div class="matchup-controls">
        <label><span>Home team</span><select id="matchup-attacker">${options}</select></label>
        <button id="matchup-swap" type="button" aria-label="Reverse venue">⇄</button>
        <label><span>Away team</span><select id="matchup-defender">${options}</select></label>
      </div>
      <div class="matchup-identities">
        <div class="matchup-identity attack"><span class="panel-label">Home profile</span><strong id="attacker-name"></strong><small id="attacker-type"></small></div>
        <div class="matchup-identity defence"><span class="panel-label">Away profile</span><strong id="defender-name"></strong><small id="defender-type"></small></div>
        <div class="best-route" id="matchup-best-route"></div>
      </div>
      <div class="matchup-source" id="matchup-probability-source" role="status"></div>
      <div class="round-robin-probability" id="round-robin-probability"></div>
      <div class="route-head"><span>Route</span><span>Attack expression</span><span>Opponent exposure</span><span>XI execution edge</span><span>Current read</span></div>
      <div id="matchup-route-rows"></div>
      <div class="matchup-foot"><span>Read = 70% route fit + 30% XI execution</span><span>Positive = favorable</span><span>Negative = resisted</span><span>Projected XI uses locked Player Alpha components</span></div>
    </section>
    <section class="section"><div class="section-head"><h2>Expected 38-match table</h2><span class="panel-label">Benchmark · ${esc(dateOnly(data.round_robin.meta.as_of))}</span></div><div class="table-shell round-robin-table"><table><thead><tr><th>#</th><th>Club</th><th>W</th><th>D</th><th>L</th><th>Pts</th><th>xGD</th></tr></thead><tbody>${roundRobinTable(data.round_robin)}</tbody></table></div><p class="clean-note">This is a fixed-strength benchmark across ${data.round_robin.meta.total_match_simulations.toLocaleString()} simulations, not a season forecast. The tactical comparison above uses the style snapshot dated ${esc(dateOnly(snapshot.as_of))}.</p></section>
    <section class="section"><div class="section-head"><h2>Current Premier League archetypes</h2><span class="panel-label">Recency-weighted through ${esc(snapshot.as_of)}</span></div><div class="archetype-grid">${archetypeCards(snapshot)}</div></section>`;
}

function methodology() {
  return `${pageHead("About Clubalpha", "Methodology",
    "We publish pre-match forecasts and compare them with final results. All positions are simulated.")}
    <p class="clean-note"><a href="/matchups/">Explore matchup probabilities</a></p>`;
}

function holyGrail() {
  return `${pageHead("Research archive", "Holy Grail",
    "The original research is archived. Matchups is the place to explore current fixture forecasts and playing styles.")}
    <p class="clean-note"><a href="/matchups/">Open Matchups</a></p>`;
}

async function start() {
  const route = routeName();
  activateNav(route);
  try {
    const file = route === "matchups" ? "matchups" : "dashboard";
    const response = await fetch(`/data/${file}.json`, { cache: "no-store" });
    if (!response.ok) throw new Error(`Data request failed (${response.status})`);
    const data = await response.json();
    const views = { overview, predictions, ucl, "holy-grail": holyGrail, matchups, ledger, methodology };
    app.innerHTML = (views[route] || overview)(data);
    if (route === "matchups") {
      const attacker = document.querySelector("#matchup-attacker");
      const defender = document.querySelector("#matchup-defender");
      const query = new URLSearchParams(location.search);
      const first = data.slate?.fixtures[0];
      const home = query.get("home") || first?.home_team || "Manchester City";
      const away = query.get("away") || first?.away_team || "Crystal Palace";
      if (attacker && snapshotTeam(data.style_matchup, home)) attacker.value = home;
      if (defender && snapshotTeam(data.style_matchup, away)) defender.value = away;
      bindMatchups(data.style_matchup, data.round_robin, data.slate);
    }
    document.title = `${route === "overview" ? "Clubalpha" : route === "ucl" ? "UCL" : route[0].toUpperCase() + route.slice(1)} — Clubalpha`;
  } catch (error) {
    app.innerHTML = `<div class="error">Clubalpha could not load its frozen artifact: ${esc(error.message)}</div>`;
  }
}

function snapshotTeam(snapshot, name) {
  return snapshot.teams.some((team) => team.team === name);
}

start();
