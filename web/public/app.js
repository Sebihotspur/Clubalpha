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
    timeZone: "UTC",
    timeZoneName: "short",
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

function metric(label, value, note, tone = "") {
  return `<div class="metric"><span class="label">${esc(label)}</span><strong class="${tone}">${esc(value)}</strong><small>${esc(note)}</small></div>`;
}

function resultPills(match) {
  const results = [
    ["H", match.probabilities.home_win],
    ["D", match.probabilities.draw],
    ["A", match.probabilities.away_win],
  ];
  const best = Math.max(...results.map(([, value]) => value));
  return `<div class="result-pills">${results
    .map(
      ([label, value]) =>
        `<div class="result-pill ${value === best ? "best" : ""}"><span>${label}</span><strong>${pct(value)}</strong></div>`,
    )
    .join("")}</div>`;
}

function topMatchCards(matches) {
  return matches
    .slice()
    .sort((a, b) => b.predicted_xg.total - a.predicted_xg.total)
    .slice(0, 6)
    .map(
      (match) => `<article class="match-card">
        <div class="match-time">${esc(dateTime(match.kickoff_utc))}</div>
        <div class="match-teams"><span>${esc(match.home_team)}</span><span>${esc(match.away_team)}</span></div>
        <div class="xg-row">
          <div><span class="panel-label">Projected total xG</span><div class="xg-total">${dec(match.predicted_xg.total)}</div></div>
          <div class="lean">Intelligence lean<strong>${esc(match.lean || "No consensus")} · ${match.support}/3</strong></div>
        </div>
      </article>`,
    )
    .join("");
}

function overview(data) {
  const pick = data.official_shadow_pick;
  return `
    <section class="hero">
      <div>
        <p class="eyebrow">Premier League + Champions League</p>
        <h1>Football intelligence,<br /><span>earned in public.</span></h1>
        <p class="hero-copy">Player quality, current squad form, and relevant fixture history—converted into transparent shadow probabilities before a single unit of real capital is authorized.</p>
      </div>
      <aside class="hero-note">
        <span class="label">Current operating state</span>
        <strong>OBSERVE · FREEZE · SCORE</strong>
        <p>Matchdays 2–5 are evidence collection. The ledger evaluates the model; the model does not grade itself after the result.</p>
      </aside>
    </section>

    <section class="metrics">
      ${metric("Deployment", "NO CAPITAL", "Shadow observations only", "amber")}
      ${metric("Simulation", data.meta.simulations.toLocaleString(), "Independent Poisson runs", "accent")}
      ${metric("Frozen slate", `${data.meta.fixture_count} fixtures`, `As of ${data.meta.as_of}`)}
      ${metric("Validation", `${data.ledger.matches_logged}/${data.ledger.sample_gate}`, "Goal-model match gate")}
    </section>

    <section class="section">
      <div class="section-head"><h2>Official shadow observation</h2><a href="/ledger/">Open ledger →</a></div>
      <article class="pick-card">
        <div class="pick-main">
          <div class="pick-tag"><span></span> Frozen before kickoff · zero real units</div>
          <p class="fixture-kicker">${esc(dateTime(pick.kickoff_utc))}</p>
          <h2 class="pick-title">${esc(pick.fixture)}</h2>
          <div class="pick-market">${esc(pick.market)}</div>
          <div class="pick-reasons">
            ${pick.reasons.map((reason) => `<div class="reason"><strong>${esc(reason.value)}</strong><span>${esc(reason.label)}</span></div>`).join("")}
          </div>
        </div>
        <div class="pick-numbers">
          <div class="pick-number"><span class="label">Model probability</span><strong class="green">${pct(pick.model_probability)}</strong><small>Shadow estimate</small></div>
          <div class="pick-number"><span class="label">Model fair price</span><strong>${dec(pick.fair_decimal)}</strong><small>Before uncertainty buffer</small></div>
          <div class="pick-number"><span class="label">Qualifying price</span><strong class="yellow">${dec(pick.minimum_price)}+</strong><small>Record only if observed</small></div>
          <div class="pick-number"><span class="label">Shadow allocation</span><strong>${dec(pick.shadow_units)}u</strong><small>Real allocation: 0.00u</small></div>
        </div>
      </article>
    </section>

    <section class="section">
      <div class="section-head"><h2>Highest projected goal environments</h2><a href="/predictions/">All predictions →</a></div>
      <div class="card-grid">${topMatchCards(data.predictions)}</div>
    </section>

    <section class="section">
      <div class="section-head"><h2>Three intelligence foundations</h2><a href="/methodology/">Methodology →</a></div>
      <div class="foundation-grid">
        ${data.methodology.components.map((component, index) => `<article class="foundation-card"><span class="foundation-num">0${index + 1} · ${component.weight}%</span><h3>${esc(component.name)}</h3><p>${esc(component.description)}</p><div class="weight-line"><span style="width:${component.weight}%"></span></div></article>`).join("")}
      </div>
    </section>

    <section class="section">
      <div class="section-head"><h2>Style Matchup v0</h2><a href="/matchups/">Explore vulnerabilities →</a></div>
      <article class="matchup-teaser">
        <div><span class="panel-label">New research challenger · zero composite weight</span><h3>How can one team make the next opponent vulnerable?</h3><p>Compare five attacking routes against the opponent’s measured exposure, then confirm whether the projected XI has the player quality to execute.</p></div>
        <div class="teaser-flow"><span>STYLE ROUTE</span><i>×</i><span>OPPONENT EXPOSURE</span><i>×</i><span>PLAYER ALPHA</span></div>
      </article>
    </section>`;
}

function predictions(data) {
  const rows = data.predictions
    .map(
      (match) => `<tr>
        <td class="fixture-cell"><strong>${esc(match.home_team)} vs ${esc(match.away_team)}</strong><span>${esc(dateTime(match.kickoff_utc))} · ${esc(match.top_scoreline)}</span></td>
        <td>${dec(match.predicted_xg.home)}–${dec(match.predicted_xg.away)}</td>
        <td>${resultPills(match)}</td>
        <td class="prob-over">${pct(match.probabilities.over_2_5)}</td>
        <td>${pct(match.probabilities.btts_yes)}</td>
        <td>${esc(match.lean || "—")} · ${match.support}/3</td>
        <td><span class="status-chip ${match.official_pick ? "official" : ""}">${match.official_pick ? "Official pick" : "Monitor"}</span></td>
      </tr>`,
    )
    .join("");

  return `<section class="page-head"><p class="eyebrow">Fixture probability slate</p><h1>Predictions</h1><p>Frozen 2026–27 Premier League Matchday 2 probabilities. Every number uses the same dated inputs and 50,000 simulations; none is a market recommendation.</p><div class="notice">SHADOW ONLY · Lineups are projected priors, not confirmed XIs · No price means no edge · No edge means no allocation</div></section>
    <div class="table-shell"><table><thead><tr><th>Fixture</th><th>Model xG</th><th>1X2 probability</th><th>O2.5</th><th>BTTS</th><th>Layer consensus</th><th>Status</th></tr></thead><tbody>${rows}</tbody></table></div>
    <p class="notice">Model probabilities are not bookmaker prices. The first slate remains below both validation gates: ${data.meta.scale_training_sides}/${data.meta.scale_validation_sides} component-scale sides and ${data.meta.goal_training_matches}/${data.meta.goal_validation_matches} goal-calibration matches.</p>`;
}

function ledger(data) {
  const pick = data.official_shadow_pick;
  const progress = Math.min(100, (data.ledger.matches_logged / data.ledger.sample_gate) * 100);
  const slateRows = data.predictions
    .map(
      (match) => `<tr><td class="fixture-cell"><strong>${esc(match.home_team)} vs ${esc(match.away_team)}</strong><span>${esc(dateTime(match.kickoff_utc))}</span></td><td>${match.official_pick ? esc(pick.market) : "Full forecast frozen"}</td><td>${match.official_pick ? pct(pick.model_probability) : `${pct(Math.max(match.probabilities.home_win, match.probabilities.draw, match.probabilities.away_win))} top 1X2`}</td><td>${match.official_pick ? `${dec(pick.minimum_price)}+` : "—"}</td><td><span class="status-chip ${match.official_pick ? "official" : ""}">Pending</span></td></tr>`,
    )
    .join("");
  return `<section class="page-head"><p class="eyebrow">Immutable public record</p><h1>Shadow ledger</h1><p>We publish the observation before kickoff, append the result afterward, and measure whether Clubalpha improves on simple baselines. No selection can be added retroactively.</p></section>
    <div class="ledger-hero">
      <article class="ledger-panel"><span class="panel-label">Capital readiness</span><h2>NO GO <span>· ${data.ledger.matches_logged}/${data.ledger.sample_gate}</span></h2><p>Matchday 4 or 5 is a review checkpoint—not an automatic authorization date. The evidence must earn the transition.</p><div class="progress"><span style="width:${progress}%"></span></div></article>
      <article class="ledger-panel"><span class="panel-label">What will be scored</span><div class="gate-list">${data.ledger.scorecards.map((item) => `<div class="gate-row"><span>${esc(item)}</span><span>Pending</span></div>`).join("")}</div></article>
    </div>
    <section class="section"><div class="section-head"><h2>Frozen Matchday 2 slate</h2><span class="panel-label">Results append after full time</span></div><div class="table-shell"><table><thead><tr><th>Fixture</th><th>Observation</th><th>Frozen probability</th><th>Price gate</th><th>Result</th></tr></thead><tbody>${slateRows}</tbody></table></div></section>`;
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

function renderMatchup(snapshot, roundRobin) {
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
  const probability = roundRobin.fixtures.find(
    (fixture) => fixture.home_team === attacker.team && fixture.away_team === defender.team,
  );
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

function bindMatchups(snapshot, roundRobin) {
  const attacker = document.querySelector("#matchup-attacker");
  const defender = document.querySelector("#matchup-defender");
  if (!attacker || !defender) return;
  attacker.addEventListener("change", () => renderMatchup(snapshot, roundRobin));
  defender.addEventListener("change", () => renderMatchup(snapshot, roundRobin));
  document.querySelector("#matchup-swap").addEventListener("click", () => {
    const previous = attacker.value;
    attacker.value = defender.value;
    defender.value = previous;
    renderMatchup(snapshot, roundRobin);
  });
  renderMatchup(snapshot, roundRobin);
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
  return `<section class="page-head"><p class="eyebrow">380-fixture shadow round robin · ${esc(snapshot.as_of)}</p><h1>Matchup probabilities</h1><p>Choose any home and away team to see the current win/draw/loss probabilities, expected goals, and the route that can make the opponent vulnerable.</p><div class="notice">SHADOW BENCHMARK · Today’s form and projected squads are held constant for all 38 matches · Style Matchup remains zero weight in the locked 60/30/10 model</div></section>
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
      <div class="round-robin-probability" id="round-robin-probability"></div>
      <div class="route-head"><span>Route</span><span>Attack expression</span><span>Opponent exposure</span><span>XI execution edge</span><span>Current read</span></div>
      <div id="matchup-route-rows"></div>
      <div class="matchup-foot"><span>Read = 70% route fit + 30% XI execution</span><span>Positive = favorable</span><span>Negative = resisted</span><span>Projected XI uses locked Player Alpha components</span></div>
    </section>
    <section class="section"><div class="section-head"><h2>Expected 38-match table</h2><span class="panel-label">${data.round_robin.meta.total_match_simulations.toLocaleString()} match simulations</span></div><div class="table-shell round-robin-table"><table><thead><tr><th>#</th><th>Club</th><th>W</th><th>D</th><th>L</th><th>Pts</th><th>xGD</th></tr></thead><tbody>${roundRobinTable(data.round_robin)}</tbody></table></div><p class="notice">This is a fixed-strength diagnostic table, not a season forecast: form, injuries, transfers and lineups do not evolve between fixtures.</p></section>
    <section class="section"><div class="section-head"><h2>Current Premier League archetypes</h2><span class="panel-label">Recency-weighted through ${esc(snapshot.as_of)}</span></div><div class="archetype-grid">${archetypeCards(snapshot)}</div></section>`;
}

function methodology(data) {
  return `<section class="page-head"><p class="eyebrow">Transparent by design</p><h1>Methodology</h1><p>Simple foundations, strict chronology, and visible refusal rules. Player Quality remains locked; calibration sits downstream and cannot rewrite the intelligence after seeing a result.</p></section>
    <div class="method-stack">
      <article class="method-card"><div class="step">01 · Intelligence</div><div><h2>Score the matchup from three foundations</h2><p>Club Form captures current attack and defence, Player Quality grades projected minutes using the locked positional Alpha formulas, and Historical Fixtures supplies a deliberately small venue and matchup residual.</p><div class="formula">fixture signal = 0.60 × club form\n               + 0.30 × projected-XI player quality\n               + 0.10 × historical residual</div></div></article>
      <article class="method-card"><div class="step">02 · Goal model</div><div><h2>Adjust the competition scoring environment</h2><p>The Premier League home and away xG baseline remains outside the composite. A separately versioned coefficient translates the normalized fixture signal into expected goals.</p><div class="formula">predicted xG = competition baseline xG × exp(β × fixture signal)</div></div></article>
      <article class="method-card"><div class="step">03 · Simulation</div><div><h2>Run 50,000 transparent match simulations</h2><p>Independent Poisson is the conservative v0 baseline. It produces 1X2, totals, BTTS, and scoreline distributions. More complex correlation models must improve fresh chronological tests before adoption.</p></div></article>
      <article class="method-card"><div class="step">04 · Ledger</div><div><h2>Freeze, observe, and earn capital readiness</h2><p>Forecasts are immutable. After full time, the ledger appends score, FotMob xG, lineups, closing price, and calibration metrics. Capital deployment remains false until the gates pass.</p><div class="caveats">${data.methodology.caveats.map((item) => `<div class="caveat">${esc(item)}</div>`).join("")}</div></div></article>
    </div>`;
}

async function start() {
  const route = routeName();
  activateNav(route);
  try {
    const response = await fetch("/data/site.json", { cache: "no-store" });
    if (!response.ok) throw new Error(`Data request failed (${response.status})`);
    const data = await response.json();
    const views = { overview, predictions, matchups, ledger, methodology };
    app.innerHTML = (views[route] || overview)(data);
    if (route === "matchups") {
      const attacker = document.querySelector("#matchup-attacker");
      const defender = document.querySelector("#matchup-defender");
      if (attacker && snapshotTeam(data.style_matchup, "Manchester City")) attacker.value = "Manchester City";
      if (defender && snapshotTeam(data.style_matchup, "Crystal Palace")) defender.value = "Crystal Palace";
      bindMatchups(data.style_matchup, data.round_robin);
    }
    document.title = `${route === "overview" ? "Clubalpha" : route[0].toUpperCase() + route.slice(1)} — Clubalpha`;
  } catch (error) {
    app.innerHTML = `<div class="error">Clubalpha could not load its frozen artifact: ${esc(error.message)}</div>`;
  }
}

function snapshotTeam(snapshot, name) {
  return snapshot.teams.some((team) => team.team === name);
}

start();
