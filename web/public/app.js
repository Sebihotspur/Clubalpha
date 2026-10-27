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
const pp = (value) => `${Number(value) >= 0 ? "+" : ""}${(Number(value) * 100).toFixed(1)} pp`;
const signedPct = (value) => `${Number(value) >= 0 ? "+" : ""}${(Number(value) * 100).toFixed(1)}%`;
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
const dateOnly = (value) =>
  new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
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
    ["H", "home_win", match.probabilities.home_win],
    ["D", "draw", match.probabilities.draw],
    ["A", "away_win", match.probabilities.away_win],
  ];
  const best = Math.max(...results.map(([, , value]) => value));
  return `<div class="result-pills">${results
    .map(
      ([label, outcome, value]) =>
        `<div class="result-pill ${value === best ? "best" : ""} ${match.official_pick?.outcome === outcome ? "official-choice" : ""}"><span>${label}</span><strong>${pct(value)}</strong></div>`,
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
          <div class="lean">Official prediction<strong>${esc(match.official_pick.primary_read)} · ${esc(match.official_pick.confidence)}</strong></div>
        </div>
      </article>`,
    )
    .join("");
}

function currentResearchCards(matches) {
  return matches
    .slice()
    .sort((a, b) => b.predicted_xg.total - a.predicted_xg.total)
    .slice(0, 6)
    .map((match) => {
      const leader = ["home_win", "draw", "away_win"].sort(
        (a, b) => match.probabilities[b] - match.probabilities[a],
      )[0];
      const label = leader === "home_win" ? match.home_team : leader === "away_win" ? match.away_team : "Draw";
      return `<article class="match-card">
        <div class="match-time">${esc(dateTime(match.kickoff_utc))}</div>
        <div class="match-teams"><span>${esc(match.home_team)}</span><span>${esc(match.away_team)}</span></div>
        <div class="xg-row">
          <div><span class="panel-label">Projected total xG</span><div class="xg-total">${dec(match.predicted_xg.total)}</div></div>
          <div class="lean">Final calibrated call<strong>${esc(label)} · ${pct(match.probabilities[leader])}</strong></div>
        </div>
      </article>`;
    })
    .join("");
}

function overview(data) {
  const latest = data.latest_matchweek;
  const upcoming = data.provisional_matchweek;
  const side = latest.score.markets.one_x_two;
  const totals = latest.score.markets.over_under_2_5;
  const contextReinforcements = data.holy_grail.predictions.filter(
    (match) => match.verdict === "baseline_reinforced",
  ).length;
  return `
    <section class="hero">
      <div>
        <p class="eyebrow">Premier League + Champions League</p>
        <h1>Football intelligence,<br /><span>earned in public.</span></h1>
        <p class="hero-copy">Player quality, current squad form, and relevant fixture history—converted into transparent shadow probabilities before a single unit of real capital is authorized.</p>
      </div>
      <aside class="hero-note">
        <span class="label">Current operating state</span>
        <strong>PROJECT · REFUSE · REFRESH</strong>
        <p>Matchweek ${esc(upcoming.round)} is provisional. Thirteen clubs still play EFL Cup fixtures before the league slate, so the model has published directions but blocked the final freeze.</p>
      </aside>
    </section>

    <section class="metrics">
      ${metric("Deployment", "NO CAPITAL", "Shadow observations only", "amber")}
      ${metric(`MW${latest.round} 1X2 calls`, `${side.hits}/${side.settled}`, pct(side.hit_rate), "amber")}
      ${metric(`MW${latest.round} totals calls`, `${totals.hits}/${totals.settled}`, pct(totals.hit_rate), totals.hit_rate >= 0.5 ? "accent" : "amber")}
      ${metric("Learning memory", `${data.methodology.research_loop.adaptive.match_learning_cards} matches`, "Completed evidence only")}
    </section>

    <section class="section">
      <div class="section-head"><h2>Matchweek ${esc(upcoming.round)} provisional slate</h2><a href="/predictions/">Open all 10 forecasts →</a></div>
      <div class="foundation-grid">
        <article class="foundation-card"><span class="foundation-num">1X2</span><h3>${upcoming.summary.side_calls} calls · ${upcoming.summary.side_passes} passes</h3><p>No side currently satisfies every probability, separation, Club Form, Player Alpha, context and lineup gate.</p></article>
        <article class="foundation-card"><span class="foundation-num">O/U 2.5</span><h3>${upcoming.summary.totals_calls} calls · ${upcoming.summary.totals_passes} passes</h3><p>Manchester City–Brighton Over and Liverpool–Arsenal Under are the only provisional totals above the 58% boundary.</p></article>
        <article class="foundation-card"><span class="foundation-num">REFRESH GATE</span><h3>${upcoming.pending_preleague_teams.length} teams pending</h3><p>Final predictions wait until every October 27–29 EFL Cup fixture and its lineup evidence is ingested.</p></article>
      </div>
      <p class="notice">PROVISIONAL ONLY · Final call eligibility is ${upcoming.decision_boundaries.final_call_eligible ? "open" : "blocked"} · Real allocation remains 0.00u.</p>
    </section>

    <section class="section">
      <div class="section-head"><h2>Matchweek ${esc(latest.round)} accuracy review</h2><a href="/predictions/">Open all 10 results →</a></div>
      <article class="pick-card">
        <div class="pick-main">
          <div class="pick-tag"><span></span> SETTLED · PUBLISHED PROVISIONAL SLATE</div>
          <p class="fixture-kicker">RESULT · XG PROCESS · LINEUP ACCURACY · ERROR ATTRIBUTION</p>
          <h2 class="pick-title">The pass gate helped; promoted sides did not</h2>
          <div class="pick-market">Five side passes avoided five losing leans. The one promoted side hit was Arsenal; the accuracy shortlist finished ${latest.shortlist_score.hits}/${latest.shortlist_score.settled}.</div>
          <div class="pick-reasons">
            <div class="reason"><strong>${side.hits}/${side.settled}</strong><span>promoted sides</span></div>
            <div class="reason"><strong>${totals.hits}/${totals.settled}</strong><span>promoted totals</span></div>
            <div class="reason"><strong>${dec(latest.backtest_summary.mean_projected_xi_hits_of_11)}/11</strong><span>projected-XI hits</span></div>
          </div>
        </div>
        <div class="pick-numbers">
          <div class="pick-number"><span class="label">Base leaders</span><strong>${latest.backtest_summary.base_outcome_hits}/10</strong><small>Before context</small></div>
          <div class="pick-number"><span class="label">Context leaders</span><strong>${latest.backtest_summary.contextual_outcome_hits}/10</strong><small>Raw leaders only</small></div>
          <div class="pick-number"><span class="label">Observed xG</span><strong>${dec(latest.backtest_summary.observed_mean_total_xg)}</strong><small>vs ${dec(latest.backtest_summary.predicted_mean_total_xg)} projected</small></div>
          <div class="pick-number"><span class="label">Real allocation</span><strong>0.00u</strong><small>Capital remains locked</small></div>
        </div>
      </article>
      <p class="notice">AUDIT CAVEAT · ${esc(latest.audit_caveat)}</p>
    </section>

    <section class="section">
      <div class="section-head"><h2>What enters the next forecast</h2><a href="/methodology/">Updated methodology →</a></div>
      <div class="foundation-grid">
        <article class="foundation-card"><span class="foundation-num">FAST MEMORY</span><h3>Mandatory lineup refresh</h3><p>No final slate can freeze while a projected team still has a pending preleague fixture.</p></article>
        <article class="foundation-card"><span class="foundation-num">MEDIUM MEMORY</span><h3>Selective side promotion</h3><p>Club Form and projected-XI Player Alpha must support the same side; leaders below 45% remain passes.</p></article>
        <article class="foundation-card"><span class="foundation-num">SLOW MEMORY</span><h3>Venue, draw and tempo</h3><p>Seventy completed forecasts now shrink home bias, lift draw pressure and conservatively lower total xG.</p></article>
      </div>
    </section>

    <section class="section">
      <div class="section-head"><h2>Three intelligence foundations</h2><a href="/methodology/">Methodology →</a></div>
      <div class="foundation-grid">
        ${data.methodology.components.map((component, index) => `<article class="foundation-card"><span class="foundation-num">0${index + 1} · ${component.weight}%</span><h3>${esc(component.name)}</h3><p>${esc(component.description)}</p><div class="weight-line"><span style="width:${component.weight}%"></span></div></article>`).join("")}
      </div>
    </section>

    <section class="section">
      <div class="section-head"><h2>Holy Grail v1</h2><a href="/holy-grail/">Open contextual slate →</a></div>
      <article class="holy-teaser">
        <div>
          <span class="panel-label">Frozen contextual experiment · ${esc(dateTime(data.holy_grail.as_of))}</span>
          <h3>The foundation stays anchored. The matchup changes the scoring environment.</h3>
          <p>Each attack is evaluated against the opponent’s route exposure, projected-XI execution, and evidence reliability before the 50,000-match simulation is rerun.</p>
        </div>
        <div class="holy-teaser-read">
          <span>Archived experiment</span>
          <strong>${contextReinforcements} reinforced</strong>
          <small>The original contextual slate and its baseline remain immutable.</small>
        </div>
      </article>
    </section>

    <section class="section">
      <div class="section-head"><h2>Style Matchup v0</h2><a href="/matchups/">Explore vulnerabilities →</a></div>
      <article class="matchup-teaser">
        <div><span class="panel-label">New research challenger · zero composite weight</span><h3>How can one team make the next opponent vulnerable?</h3><p>Compare five attacking routes against the opponent’s measured exposure, then confirm whether the projected XI has the player quality to execute.</p></div>
        <div class="teaser-flow"><span>STYLE ROUTE</span><i>×</i><span>OPPONENT EXPOSURE</span><i>×</i><span>PLAYER ALPHA</span></div>
      </article>
    </section>`;
}

function uclResultRows(matches) {
  return matches
    .map((match) => {
      if (match.status !== "completed") {
        return `<tr><td class="fixture-cell"><strong>${esc(match.home_team)} vs ${esc(match.away_team)}</strong><span>${esc(dateTime(match.kickoff_utc))}</span></td><td><span class="status-chip">Pending</span></td><td>—</td><td>Awaiting full match card</td></tr>`;
      }
      const process = match.score_xg_aligned ? "Score + xG aligned" : "Outcome exceeded process";
      return `<tr>
        <td class="fixture-cell"><strong>${esc(match.home_team)} vs ${esc(match.away_team)}</strong><span>${esc(dateTime(match.kickoff_utc))}</span></td>
        <td class="ucl-score">${match.score.home}–${match.score.away}</td>
        <td>${dec(match.xg.home)}–${dec(match.xg.away)}</td>
        <td><span class="status-chip ${match.score_xg_aligned ? "hit" : "miss"}">${esc(process)}</span><small class="ucl-residual">Goals − xG ${signed(match.goal_residual)}</small></td>
      </tr>`;
    })
    .join("");
}

function uclPlayerRows(players) {
  return players
    .slice(0, 10)
    .map((player) => `<tr>
      <td class="fixture-cell"><strong>${esc(player.player)}</strong><span>${esc(player.team)} · ${esc(player.alpha_position || "unmapped")}</span></td>
      <td class="prob-main">${dec(player.rating)}</td>
      <td>${player.goals}G · ${player.assists}A</td>
      <td>${player.xg === null ? "—" : dec(player.xg)} / ${player.xa === null ? "—" : dec(player.xa)}</td>
      <td>${player.alpha_ability_z === null ? "—" : signed(player.alpha_ability_z)}</td>
      <td>${player.pillars.scoring_threat === null ? "—" : signed(player.pillars.scoring_threat)}</td>
      <td>${player.pillars.chance_creation === null ? "—" : signed(player.pillars.chance_creation)}</td>
    </tr>`)
    .join("");
}

function uclLegacy(data) {
  const review = data.ucl_matchday;
  const aggregate = review.aggregate;
  const alpha = review.player_alpha;
  const scope = review.scope;
  const watch = review.cross_competition_watch;
  const statusLabel = review.status === "complete" ? "MATCHDAY COMPLETE" : "MATCHDAY IN PROGRESS";
  const overRate = scope.completed_matches ? aggregate.over_2_5 / scope.completed_matches : 0;
  const bttsRate = scope.completed_matches ? aggregate.btts / scope.completed_matches : 0;
  const pl = review.premier_league_clubs;
  const lessons = review.tactical_archetype_lessons || {};
  const alignment = lessons.result_process_alignment || {};
  const transitionTeams = (lessons.lower_possession_process_winners || []).join(", ");
  const setPieceSpikes = (lessons.set_piece_xg_spikes || [])
    .slice(0, 4)
    .map((item) => `<div class="gate-row"><span>${esc(item.team)} vs ${esc(item.opponent)}</span><span>${dec(item.set_piece_xg)} xG</span></div>`)
    .join("");
  const varianceRows = (alignment.variance_watch || [])
    .map((item) => `<div class="gate-row"><span>${esc(item.fixture)}</span><span>score ≠ xG</span></div>`)
    .join("");
  const plReads = (pl.research_reads || [])
    .map((team) => `<div class="gate-row"><span><strong>${esc(team.team)}</strong> · ${esc(team.score)} vs ${esc(team.opponent)}</span><span>${signed(team.xg_difference)} xG · ${esc(team.observed_routes.join(" / ").replaceAll("_", " "))}</span></div>`)
    .join("");
  const coverageRows = alpha.lowest_team_coverage
    .map((team) => `<div class="gate-row"><span>${esc(team.team)}</span><span>${pct(team.coverage)}</span></div>`)
    .join("");
  const watchPlayers = watch
    ? watch.top_players.slice(0, 4).map((player) => `<div class="reason"><strong>${dec(player.rating)}</strong><span>${esc(player.player)} · ${player.goals}G ${player.assists}A</span></div>`).join("")
    : "";
  return `<section class="page-head ucl-page-head">
      <p class="eyebrow">Champions League · Matchday ${esc(review.matchday)}</p>
      <h1>European intelligence</h1>
      <p>Every completed match card feeds shared team, lineup and player-role research. UCL calibration remains separate, and no retroactive prediction record is manufactured.</p>
      <div class="notice">${esc(statusLabel)} · ${scope.completed_matches}/${scope.scheduled_matches} COMPLETE · ${scope.pending_matches} PENDING · OBSERVATIONAL EVIDENCE ONLY</div>
    </section>

    <section class="metrics">
      ${metric("Completed", `${scope.completed_matches}/${scope.scheduled_matches}`, "Matchday 1 fixtures", "accent")}
      ${metric("Goals", String(aggregate.goals), `${dec(aggregate.goals_per_match)} per completed match`)}
      ${metric("Over 2.5", pct(overRate), `${aggregate.over_2_5}/${scope.completed_matches} matches`, "amber")}
      ${metric("BTTS", pct(bttsRate), `${aggregate.btts}/${scope.completed_matches} matches`)}
    </section>

    <section class="ucl-insight-grid">
      <article class="ledger-panel"><span class="panel-label">Process versus outcome</span><h2>${aggregate.score_xg_winner_alignment}/${scope.completed_matches} <span>aligned</span></h2><p>Score outcome and FotMob xG direction agreed in ${aggregate.score_xg_winner_alignment} matches. Goals finished ${signed(aggregate.goals_minus_xg)} above xG, so the round ran hot and does not justify a permanent goals-baseline increase.</p></article>
      <article class="ledger-panel"><span class="panel-label">Player Alpha read</span><h2>${pct(alpha.actual_minute_coverage)} <span>minute coverage</span></h2><p>Alpha-to-match-rating correlation is ${dec(alpha.rating_alpha_correlation, 3)}. The top Alpha quartile averaged ${dec(alpha.top_alpha_quartile_average_rating)} versus ${dec(alpha.bottom_alpha_quartile_average_rating)} for the bottom quartile.</p></article>
      <article class="ledger-panel"><span class="panel-label">Premier League crossover</span><h2>${pl.wins}/${pl.completed_matches} <span>wins</span></h2><p>PL clubs produced ${dec(pl.xg_for)} xG and allowed ${dec(pl.xg_against)}. This strengthens shared form and matchup evidence, never the PL prediction ledger.</p></article>
      <article class="ledger-panel"><span class="panel-label">Coverage queue</span><div class="gate-list">${coverageRows}</div></article>
    </section>

    <section class="section"><div class="section-head"><h2>What Matchday 1 taught us</h2><span class="panel-label">Measured context · zero weight promotion</span></div><div class="ucl-insight-grid">
      <article class="ledger-panel"><span class="panel-label">Direct-transition evidence</span><h3>Low possession did not mean weak process</h3><p>${esc(transitionTeams || "No qualifying teams")} won both the score and xG contest with under 50% possession. Matchup route matters more than possession alone.</p></article>
      <article class="ledger-panel"><span class="panel-label">Set-piece pressure</span><div class="gate-list">${setPieceSpikes || "<p>No ≥0.75 xG spikes.</p>"}</div></article>
      <article class="ledger-panel"><span class="panel-label">Variance watch</span><div class="gate-list">${varianceRows || "<p>No score/xG direction conflicts.</p>"}</div></article>
      <article class="ledger-panel"><span class="panel-label">High-press boundary</span><h3>Not promoted</h3><p>${esc(lessons.high_pressing_status || "Pressure evidence remains incomplete.")}</p></article>
    </div></section>

    <section class="section"><div class="section-head"><h2>Premier League crossover</h2><span class="panel-label">Shared evidence · separate ledger</span></div><article class="ledger-panel"><div class="gate-list">${plReads}</div></article></section>

    <section class="section"><div class="section-head"><h2>Matchday results and process</h2><span class="panel-label">Scores are final-only</span></div><div class="table-shell"><table><thead><tr><th>Fixture</th><th>Score</th><th>FotMob xG</th><th>Research read</th></tr></thead><tbody>${uclResultRows(review.matches)}</tbody></table></div></section>

    <section class="section"><div class="section-head"><h2>Top player performances</h2><span class="panel-label">Locked Alpha attached after the match</span></div><div class="table-shell"><table><thead><tr><th>Player</th><th>Rating</th><th>Output</th><th>xG / xA</th><th>Alpha</th><th>Threat</th><th>Creation</th></tr></thead><tbody>${uclPlayerRows(alpha.top_match_ratings)}</tbody></table></div><p class="notice">PILLAR RULE · Scorer and assist research uses scoring threat and chance creation—not overall Alpha alone. ${alpha.mapped_scorers_with_positive_scoring_threat}/${alpha.mapped_scorers} mapped scorers entered with a positive scoring-threat grade.</p></section>

    ${watch ? `<section class="section"><div class="section-head"><h2>Chelsea research watch</h2><span class="panel-label">EFL Cup · excluded from PL/UCL ledgers</span></div><article class="pick-card cup-watch"><div class="pick-main"><div class="pick-tag"><span></span> CROSS-COMPETITION EVIDENCE</div><p class="fixture-kicker">${esc(dateTime(watch.kickoff_utc))}</p><h2 class="pick-title">${esc(watch.home_team)} ${esc(watch.score)} ${esc(watch.away_team)}</h2><div class="pick-market">xG ${dec(watch.xg.home)}–${dec(watch.xg.away)}</div><p class="cup-read">${esc(watch.model_read)}</p><div class="pick-reasons">${watchPlayers}</div></div><div class="pick-numbers"><div class="pick-number"><span class="label">Chelsea SOT</span><strong class="green">${dec(watch.team_stats.home.shots_on_target, 0)}</strong><small>${dec(watch.team_stats.home.big_chances, 0)} big chances</small></div><div class="pick-number"><span class="label">Leeds box touches</span><strong class="yellow">${dec(watch.team_stats.away.box_touches, 0)}</strong><small>Defensive warning</small></div><div class="pick-number"><span class="label">Leeds set-piece xG</span><strong class="yellow">${dec(watch.team_stats.away.set_piece_xg)}</strong><small>Repeatable matchup signal</small></div><div class="pick-number"><span class="label">Ledger impact</span><strong>NONE</strong><small>Research evidence only</small></div></div></article></section>` : ""}

    <p class="notice">LEARNING BOUNDARY · UCL Matchday 1 can update shared form, style, lineup and player-role evidence. It cannot rewrite Player Alpha, the 60/30/10 foundation, UCL goal calibration, or capital status after one round.</p>`;
}

function ucl(data) {
  const cycle = data.ucl_alpha_cycle;
  const evidence = cycle.completed_evidence;
  const domestic = cycle.domestic_evidence;
  const upcoming = cycle.upcoming;
  const candidateRows = upcoming.predictions.map((match) => {
    const side = match.side_research_candidate;
    const total = match.total_research_candidate;
    const leader = side.leader === "home_win" ? match.home_team : side.leader === "away_win" ? match.away_team : "Draw";
    const sideRead = side.call === "pass" ? `Pass · ${leader} lean` : `Candidate · ${leader}`;
    const totalRead = total.call === "over_2_5"
      ? `Candidate · Over 2.5 ${pct(total.call_probability)}`
      : total.call === "under_2_5"
        ? `Candidate · Under 2.5 ${pct(total.call_probability)}`
        : `Pass · O2.5 ${pct(total.over_probability)}`;
    return `<tr>
      <td class="fixture-cell"><strong>${esc(match.home_team)} vs ${esc(match.away_team)}</strong><span>${esc(dateTime(match.kickoff_utc))} · xG ${dec(match.predicted_xg.home)}–${dec(match.predicted_xg.away)}</span></td>
      <td>${resultPills(match)}</td>
      <td class="official-call"><strong>${esc(sideRead)}</strong><span>${pct(side.leader_probability)} · ${esc(side.reason.replaceAll("_", " "))}</span></td>
      <td class="official-call"><strong>${esc(totalRead)}</strong><span>${esc(total.reason.replaceAll("_", " "))}</span></td>
      <td><span class="status-chip">${esc(match.context_verdict.replaceAll("_", " "))}</span></td>
    </tr>`;
  }).join("");
  const alphaRows = cycle.projected_xi_alpha.top_clubs.map((club) => `<tr>
    <td>${club.rank}</td>
    <td class="fixture-cell"><strong>${esc(club.team)}</strong><span>${esc(club.grade)} · ${pct(club.coverage)} coverage</span></td>
    <td class="prob-main">${dec(club.strength_index, 1)}</td>
    <td>${signed(club.alpha_z, 3)}</td>
  </tr>`).join("");
  const matchdayRows = evidence.alpha_minute_coverage_by_matchday.map((row) => `<div class="gate-row"><span>Matchday ${row.matchday}</span><span>${pct(row.coverage)} coverage · ${dec(row.rating_alpha_correlation, 3)} rating correlation</span></div>`).join("");
  return `<section class="page-head ucl-page-head">
      <p class="eyebrow">Champions League · ${domestic.completed_matches} domestic matches refreshed · Matchday ${upcoming.matchday} provisional</p>
      <h1>UCL Alpha intelligence</h1>
      <p>The Champions League runs through the same projected-XI Player Alpha generator, 60/30/10 fixture foundation, matchup context and 50,000-match simulation used for the Premier League. Current domestic form is translated through the locked league-quality ladder before clubs are compared.</p>
      <div class="notice">SHARED PLAYER ALPHA · LEAGUE-STRENGTH-ADJUSTED FORM · SEPARATE UCL CALIBRATION · ZERO CAPITAL</div>
    </section>
    <section class="metrics">
      ${metric("Completed evidence", `${evidence.matches} UCL · ${domestic.completed_matches} domestic`, `${domestic.competitions} leagues · ${domestic.foreign_ucl_clubs} foreign clubs`, "accent")}
      ${metric("Projected-XI Alpha", `${cycle.projected_xi_alpha.rated_clubs}/${cycle.projected_xi_alpha.clubs} rated`, `${cycle.projected_xi_alpha.unrated_clubs.length} explicit coverage gaps`, "amber")}
      ${metric("Matchday 4", `${upcoming.simulations.toLocaleString()} simulations`, `${upcoming.fixtures} fixtures`)}
      ${metric("Deployment", "NO CAPITAL", "UCL calibration not yet available", "amber")}
    </section>
    <p class="notice">LEAGUE TRANSLATION · ${domestic.matches_with_player_detail}/${domestic.completed_matches} domestic matches include target-club player detail (${dec(domestic.player_detail_coverage_pct, 1)}%). Club Form applies the locked league-quality offset exactly once after within-league opponent adjustment; Player Alpha formulas are unchanged.</p>
    <section class="section"><div class="section-head"><h2>What the first 54 matches taught us</h2><span class="panel-label">Observed results · never retroactive predictions</span></div><div class="foundation-grid">
      <article class="foundation-card"><span class="foundation-num">GOAL ENVIRONMENT</span><h3>${evidence.goals} goals · ${dec(evidence.total_xg)} xG</h3><p>${pct(evidence.over_2_5 / evidence.matches)} finished Over 2.5. The ${signed(evidence.goals - evidence.total_xg)} goals-minus-xG gap is finishing heat, not an automatic model coefficient.</p></article>
      <article class="foundation-card"><span class="foundation-num">RESULT SHAPE</span><h3>${evidence.home_wins}H · ${evidence.draws}D · ${evidence.away_wins}A</h3><p>Score and xG winner aligned in ${evidence.score_xg_winner_alignment}/${evidence.matches} fixtures. Process remains the primary learning signal.</p></article>
      <article class="foundation-card"><span class="foundation-num">PLAYER ALPHA</span><h3>Coverage stable near 84%</h3><div class="gate-list">${matchdayRows}</div></article>
    </div></section>
    <section class="section"><div class="section-head"><h2>Matchday ${upcoming.matchday} provisional research slate</h2><span class="panel-label">${upcoming.summary.side_research_candidates} side candidates · ${upcoming.summary.total_research_candidates} totals candidates</span></div><div class="table-shell official-table"><table><thead><tr><th>Fixture</th><th>H · D · A</th><th>1X2 research</th><th>O/U 2.5 research</th><th>Context</th></tr></thead><tbody>${candidateRows}</tbody></table></div><p class="notice">CALIBRATION GATE · These are raw research candidates from the shared football stack. No UCL-specific venue, draw or tempo calibration exists yet, so none is a promoted prediction or allocation.</p></section>
    <section class="section"><div class="section-head"><h2>Current projected-XI Alpha leaders</h2><span class="panel-label">Same position formulas as Premier League · UCL-relative display index</span></div><div class="table-shell"><table><thead><tr><th>#</th><th>Club</th><th>Strength index</th><th>Projected-XI Alpha z</th></tr></thead><tbody>${alphaRows}</tbody></table></div><p class="notice">COVERAGE QUEUE · ${esc(cycle.projected_xi_alpha.unrated_clubs.join(" and "))} currently have zero mapped projected-XI Alpha coverage. They remain neutral and cannot qualify a foundation-aligned side candidate.</p></section>`;
}

function verdictLabel(value) {
  const labels = {
    baseline_reinforced: "Baseline reinforced",
    baseline_supported: "Baseline supported",
    baseline_fragile: "Baseline fragile",
    no_clear_contextual_edge: "No clear contextual edge",
  };
  return labels[value] || value;
}

function contextTone(value) {
  if (value === "baseline_reinforced") return "positive";
  if (value === "baseline_fragile") return "negative";
  return "neutral";
}

function directionRead(team, direction) {
  const xgMove = Number(direction.xg_multiplier) - 1;
  return `<div class="direction-read">
    <span>${esc(team)} · ${esc(direction.archetype)}</span>
    <strong>${esc(direction.preferred_route)}</strong>
    <small>${signedPct(xgMove)} xG · ${pct(direction.reliability)} reliability</small>
  </div>`;
}

function holyFixtureCards(matches) {
  return matches
    .map(
      (match) => `<article class="holy-fixture-card">
        <div class="holy-fixture-head">
          <span>${esc(dateTime(match.kickoff_utc))}</span>
          <span class="environment ${esc(match.goal_environment)}">${esc(match.goal_environment)}</span>
        </div>
        <div class="holy-teams">
          <strong>${esc(match.home_team)}</strong><i>vs</i><strong>${esc(match.away_team)}</strong>
        </div>
        ${resultPills(match)}
        <div class="holy-xg-bridge">
          <div><span>Base xG</span><strong>${dec(match.baseline.predicted_xg.home)}–${dec(match.baseline.predicted_xg.away)}</strong></div>
          <i>→</i>
          <div><span>Context xG</span><strong>${dec(match.predicted_xg.home)}–${dec(match.predicted_xg.away)}</strong></div>
        </div>
        <div class="context-verdict ${contextTone(match.verdict)}">
          <span>${esc(verdictLabel(match.verdict))}</span>
          <strong>${match.official_pick ? `${esc(match.official_pick.team)} · ${esc(match.official_pick.confidence)}` : `${esc(match.favorite)} · ${signedPct(match.favorite_probability_delta)}`}</strong>
        </div>
        ${match.translation_audit?.official_overrides_probability_leader ? `<div class="override-note"><strong>Audited override</strong><span>${esc(match.official_pick.override_reason)}</span></div>` : ""}
        <div class="direction-grid">
          ${directionRead(match.home_team, match.directions.home)}
          ${directionRead(match.away_team, match.directions.away)}
        </div>
        <div class="holy-markets">
          <span>O2.5 <strong>${pct(match.probabilities.over_2_5)}</strong></span>
          <span>BTTS <strong>${pct(match.probabilities.btts_yes)}</strong></span>
          <span>Score mode <strong>${esc(match.top_scoreline)}</strong></span>
        </div>
      </article>`,
    )
    .join("");
}

function holyGrail(data) {
  const model = data.holy_grail;
  const reinforced = model.predictions.filter(
    (match) => match.verdict === "baseline_reinforced",
  ).length;
  return `<section class="page-head holy-page-head">
      <p class="eyebrow">Clubalpha Contextual Interaction v1</p>
      <h1>The Holy Grail</h1>
      <p>A versatile fixture model: weighted intelligence establishes the baseline, then continuous opponent context bends each team’s scoring environment without overriding what the data already knows.</p>
      <div class="notice">FROZEN CONTEXTUAL EXPERIMENT · Original ten-fixture slate preserved as of ${esc(dateTime(model.as_of))} · No later official call rewrites this record · Zero capital authorized</div>
    </section>

    <section class="holy-summary">
      ${metric("Frozen slate", `${model.fixtures} fixtures`, `As of ${dateTime(model.as_of)}`, "accent")}
      ${metric("Simulation", model.total_simulations.toLocaleString(), "50,000 per fixture")}
      ${metric("Baseline reinforced", String(reinforced), "Continuous opponent context", "accent")}
      ${metric("Deployment", "NO CAPITAL", "Official backtest only", "amber")}
    </section>

    <section class="holy-architecture">
      <div class="holy-stage foundation-stage"><span>01 · Foundation</span><strong>60 / 30 / 10</strong><small>Form · XI Alpha · History</small></div>
      <i>→</i>
      <div class="holy-stage"><span>02 · Directional context</span><strong>Route × Exposure × XI</strong><small>Shrunk by evidence reliability</small></div>
      <i>→</i>
      <div class="holy-stage"><span>03 · xG bridge</span><strong>Base × exp(context)</strong><small>Home and away adjusted separately</small></div>
      <i>→</i>
      <div class="holy-stage"><span>04 · Simulation</span><strong>50,000 runs</strong><small>1X2 · Totals · BTTS</small></div>
    </section>

    <section class="section">
      <div class="section-head"><h2>Archived contextual fixtures</h2><span class="panel-label">Original Holy Grail experiment</span></div>
      <div class="holy-fixture-grid">${holyFixtureCards(model.predictions)}</div>
    </section>

    <p class="notice">Archetype names explain the football but never enter the mathematics. Measured channels receive more trust than partial or hypothesis channels; uncertain projected XIs shrink the adjustment automatically.</p>`;
}

function predictions(data) {
  const upcoming = data.provisional_matchweek;
  const latest = data.latest_matchweek;
  const outcomeLabel = (match, outcome) => {
    if (outcome === "home_win") return match.home_team;
    if (outcome === "away_win") return match.away_team;
    return "Draw";
  };
  const upcomingRows = upcoming.predictions
    .map((match) => {
      const sideRead = match.side_call === "pass"
        ? `Pass · ${esc(outcomeLabel(match, match.side_leader))} lean`
        : esc(outcomeLabel(match, match.side_call));
      const totalRead = match.total_call === "over_2_5"
        ? `Over 2.5 · ${pct(match.over_2_5_probability)}`
        : match.total_call === "under_2_5"
          ? `Under 2.5 · ${pct(1 - match.over_2_5_probability)}`
          : `Pass · O2.5 ${pct(match.over_2_5_probability)}`;
      const totalTone = match.total_call === "pass" ? "" : "hit";
      return `<tr>
        <td class="fixture-cell"><strong>${esc(match.home_team)} vs ${esc(match.away_team)}</strong><span>${esc(dateTime(match.kickoff_utc))} · xG ${dec(match.predicted_xg.home)}–${dec(match.predicted_xg.away)}</span></td>
        <td>${resultPills(match)}</td>
        <td class="official-call"><strong>${sideRead}</strong><span>${pct(match.side_probability)} leader · ${pct(match.side_gap)} gap</span><small>${esc(match.side_reason.replaceAll("_", " "))}</small></td>
        <td class="official-call"><strong>${totalRead}</strong><span class="status-chip ${totalTone}">${match.total_call === "pass" ? "pass" : "provisional call"}</span><small>${esc(match.total_reason.replaceAll("_", " "))}</small></td>
        <td><span class="status-chip">${esc(match.load)}</span><small>${esc(match.context_verdict.replaceAll("_", " "))}</small></td>
      </tr>`;
    })
    .join("");
  const rows = latest.predictions
    .map((match) => {
      const result = match.result;
      const sideCall = match.side_call === "pass"
        ? `Pass · ${esc(outcomeLabel(match, match.side_leader))} lean`
        : esc(outcomeLabel(match, match.side_call));
      const sideStatus = match.side_call === "pass"
        ? `<span class="status-chip hit">protected</span>`
        : `<span class="status-chip ${result.side_hit ? "hit" : "miss"}">${result.side_hit ? "hit" : "miss"}</span>`;
      const totalCall = match.total_call === "over_2_5"
        ? `Over 2.5 · ${pct(match.over_2_5_probability)}`
        : match.total_call === "under_2_5"
          ? `Under 2.5 · ${pct(1 - match.over_2_5_probability)}`
          : `Pass · O2.5 ${pct(match.over_2_5_probability)}`;
      const totalStatus = match.total_call === "pass"
        ? `<span class="status-chip">pass</span>`
        : `<span class="status-chip ${result.total_hit ? "hit" : "miss"}">${result.total_hit ? "hit" : "miss"}</span>`;
      return `<tr>
        <td class="fixture-cell"><strong>${esc(match.home_team)} vs ${esc(match.away_team)}</strong><span>${esc(dateTime(match.kickoff_utc))} · xG ${dec(match.predicted_xg.home)}–${dec(match.predicted_xg.away)}</span></td>
        <td class="official-call"><strong>${sideCall}</strong><span>${pct(match.side_probability)} leader · ${pct(match.side_gap)} gap · ${sideStatus}</span></td>
        <td class="official-call"><strong>${totalCall}</strong><span>${totalStatus} · ${esc(match.context_verdict.replaceAll("_", " "))}</span></td>
        <td><div class="ledger-result"><strong>${result.final_home_goals}–${result.final_away_goals}</strong><small>xG ${dec(result.actual_xg.home)}–${dec(result.actual_xg.away)}</small></div></td>
        <td><span class="status-chip ${result.review_class === "process_supported_outcome_variance" ? "hit" : "miss"}">${esc(result.review_class.replaceAll("_", " "))}</span></td>
      </tr>`;
    })
    .join("");
  const archivedRows = data.official_slate.predictions
    .map(
      (match) => `<tr>
        <td class="fixture-cell"><strong>${esc(match.home_team)} vs ${esc(match.away_team)}</strong><span>${esc(dateTime(match.kickoff_utc))} · model score mode ${esc(match.top_scoreline)}</span></td>
        <td>${dec(match.predicted_xg.home)}–${dec(match.predicted_xg.away)}</td>
        <td>${resultPills(match)}</td>
        <td class="prob-over">${pct(match.probabilities.over_2_5)}</td>
        <td class="official-call"><strong>${esc(match.official_pick.team)}</strong><span>${esc(match.official_pick.confidence)} conviction${match.translation_audit.official_overrides_probability_leader ? " · audited override" : ""}</span></td>
        <td class="thesis-cell">${esc(match.official_pick.thesis)}</td>
      </tr>`,
    )
    .join("");

  return `<section class="page-head"><p class="eyebrow">Provisional research slate · Matchweek ${esc(upcoming.round)}</p><h1>Next-matchweek predictions</h1><p>The refreshed engine has projected all ten fixtures through ${esc(dateOnly(upcoming.as_of))}. Thirteen clubs still play EFL Cup matches before the league slate, so every direction remains provisional until the final post-cup lineup and availability refresh.</p><div class="notice">PROVISIONAL THROUGH OCTOBER 26 · FINAL REFRESH AFTER OCTOBER 29 · ZERO CAPITAL AUTHORIZED</div></section>
    <section class="metrics">
      ${metric("1X2", `${upcoming.summary.side_calls} calls · ${upcoming.summary.side_passes} passes`, "Every side fails at least one promotion gate", "amber")}
      ${metric("O/U 2.5", `${upcoming.summary.totals_calls} calls · ${upcoming.summary.totals_passes} passes`, "Only probabilities at or beyond 58%", "accent")}
      ${metric("Refresh gate", `${upcoming.pending_preleague_teams.length} clubs pending`, "EFL Cup evidence still to ingest", "amber")}
      ${metric("Deployment", "NO CAPITAL", "Research predictions only", "amber")}
    </section>
    <section class="section"><div class="section-head"><h2>Matchweek ${esc(upcoming.round)} provisional slate</h2><span class="panel-label">${esc(dateTime(upcoming.generated_at_utc))}</span></div><div class="table-shell official-table"><table><thead><tr><th>Fixture</th><th>H · D · A</th><th>1X2 decision</th><th>O/U 2.5</th><th>Load + context</th></tr></thead><tbody>${upcomingRows}</tbody></table></div></section>
    <p class="notice">CURRENT TOTALS SHORTLIST · Manchester City–Brighton Over 2.5 at 58.1% · Liverpool–Arsenal Under 2.5 at 60.0% · No side call is promoted. Final freeze eligibility is blocked until the post-cup refresh.</p>
    <section class="page-head"><p class="eyebrow">Settled research slate · Matchweek ${esc(latest.round)}</p><h1>Predictions vs reality</h1><p>The published calls, passes and pre-match probabilities remain frozen beside the final score and xG process. Matchweek 8 adds evidence to the next forecast; it does not rewrite this one.</p><div class="notice">SETTLED PUBLISHED PROVISIONAL SLATE · 1X2 + O/U 2.5 scored only when promoted · Zero capital authorized</div></section>
    <section class="metrics">
      ${metric("Promoted 1X2", `${latest.score.markets.one_x_two.hits}/${latest.score.markets.one_x_two.settled}`, pct(latest.score.markets.one_x_two.hit_rate), "amber")}
      ${metric("Promoted O/U 2.5", `${latest.score.markets.over_under_2_5.hits}/${latest.score.markets.over_under_2_5.settled}`, pct(latest.score.markets.over_under_2_5.hit_rate), latest.score.markets.over_under_2_5.hit_rate >= 0.5 ? "accent" : "amber")}
      ${metric("Accuracy shortlist", `${latest.shortlist_score.hits}/${latest.shortlist_score.settled}`, pct(latest.shortlist_score.hit_rate), "accent")}
      ${metric("Projected XI", `${dec(latest.backtest_summary.mean_projected_xi_hits_of_11)}/11`, `${pct(latest.backtest_summary.formation_accuracy)} formation accuracy`, "accent")}
    </section>
    <section class="section"><div class="section-head"><h2>Matchweek ${esc(latest.round)} result review</h2><span class="panel-label">Updated ${esc(dateTime(latest.as_of))}</span></div><div class="table-shell official-table"><table><thead><tr><th>Fixture</th><th>1X2 decision</th><th>O/U 2.5</th><th>Result + xG</th><th>Error attribution</th></tr></thead><tbody>${rows}</tbody></table></div></section>
    <p class="notice">AUDIT CAVEAT · ${esc(latest.audit_caveat)}</p>
    <p class="notice">The pass gate avoided five losing side leans, but promoted sides finished ${latest.score.markets.one_x_two.hits}/${latest.score.markets.one_x_two.settled}. Base leaders scored ${latest.backtest_summary.base_outcome_hits}/10 and contextual leaders ${latest.backtest_summary.contextual_outcome_hits}/10. The next forecast therefore tightens side promotion, requires a post-midweek lineup refresh, and applies conservative venue, draw and total-xG calibration. Player Alpha and the 60/30/10 foundation remain locked.</p>
    <section class="section"><div class="section-head"><h2>Latest settled official archive</h2><a href="/ledger/">Open the immutable ledger →</a></div><div class="table-shell official-table"><table><thead><tr><th>Fixture</th><th>Model xG</th><th>1X2 probability</th><th>O2.5</th><th>Official call</th><th>Why</th></tr></thead><tbody>${archivedRows}</tbody></table></div></section>`;
}

function matchweekMarket(metric) {
  const value = metric.hit_rate === null ? "—" : pct(metric.hit_rate);
  const note = metric.settled
    ? `${metric.hits}/${metric.settled} correct`
    : "Awaiting results";
  return `<div class="matchweek-market">
    <span>${esc(metric.label)}</span>
    <strong>${esc(value)}</strong>
    <small>${esc(note)}</small>
  </div>`;
}

function matchweekFold(week, index) {
  const oneXTwo = week.markets.one_x_two;
  const headline = oneXTwo.hit_rate === null
    ? `${week.pending} pending`
    : `${pct(oneXTwo.hit_rate)} 1X2`;
  const gateLabel = week.counts_toward_promotion_gate
    ? "Its 1X2 results count toward the official promotion gate"
    : "Research backtest · excluded from the official promotion gate";
  return `<details class="matchweek-fold"${index === 0 ? " open" : ""}>
    <summary>
      <div class="matchweek-identity">
        <span>${esc(dateOnly(week.first_kickoff_utc))} – ${esc(dateOnly(week.last_kickoff_utc))}</span>
        <strong>${esc(week.name)}</strong>
        <small>${esc(week.source)}</small>
      </div>
      <div class="matchweek-summary">
        <span class="status-chip ${week.status === "settled" ? "official" : ""}">${esc(week.status)}</span>
        <strong>${esc(headline)}</strong>
        <i aria-hidden="true">⌄</i>
      </div>
    </summary>
    <div class="matchweek-body">
      <div class="matchweek-market-grid">
        ${matchweekMarket(week.markets.one_x_two)}
        ${matchweekMarket(week.markets.over_under_2_5)}
        ${matchweekMarket({ ...week.markets.btts, label: "BTTS diagnostic" })}
      </div>
      <div class="matchweek-foot"><span>${week.settled}/${week.fixtures} fixtures settled</span><span>${esc(gateLabel)}</span></div>
    </div>
  </details>`;
}

function ledger(data) {
  const progress = Math.min(100, (data.ledger.matches_logged / data.ledger.sample_gate) * 100);
  const displayedRate = data.ledger.hit_rate === null ? "—" : pct(data.ledger.hit_rate);
  const latestWeek = data.ledger.matchweeks[0];
  const diagnostic = data.official_slate.performance_diagnostic;
  const environment = diagnostic.observed_xg_total_range;
  const forecastEnvironment = diagnostic.projected_xg_total_range;
  const slateRows = data.official_slate.predictions
    .map(
      (match) => {
        const result = match.result;
        const resultCell = result
          ? `<div class="ledger-result"><strong>${result.final_home_goals}–${result.final_away_goals}</strong><span class="status-chip ${result.official_1x2_hit ? "hit" : "miss"}">${result.official_1x2_hit ? "1X2 hit" : "1X2 miss"}</span><small>xG ${dec(result.actual_xg.home)}–${dec(result.actual_xg.away)}</small></div>`
          : `<span class="status-chip">Pending</span>`;
        return `<tr><td class="fixture-cell"><strong>${esc(match.home_team)} vs ${esc(match.away_team)}</strong><span>${esc(dateTime(match.kickoff_utc))}</span></td><td class="official-call"><strong>${esc(match.official_pick.team)}</strong><span>${esc(match.official_pick.confidence)}</span></td><td>${pct(match.official_pick.model_probability)}</td><td>${esc(match.official_pick.secondary_read)}</td><td>${resultCell}</td></tr>`;
      },
    )
    .join("");
  const currentMisses = diagnostic.settled - diagnostic.official_1x2_hits;
  const currentPending = data.official_slate.fixtures - diagnostic.settled;
  return `<section class="page-head"><p class="eyebrow">Immutable public record</p><h1>Prediction and research ledger</h1><p>Every frozen call stays unchanged after kickoff. Official promotion evidence and newer research matchweeks remain visibly separated so learning never rewrites the historical record.</p><div class="notice">LATEST SETTLED RESEARCH · MATCHWEEK ${esc(latestWeek.matchweek)} · ${latestWeek.markets.one_x_two.hits}/${latestWeek.markets.one_x_two.settled} PROMOTED 1X2 · ${latestWeek.markets.over_under_2_5.hits}/${latestWeek.markets.over_under_2_5.settled} PROMOTED O/U 2.5 · NEXT SLATE AWAITS FINAL REFRESH</div></section>
    <div class="ledger-hero">
      <article class="ledger-panel"><span class="panel-label">Promotion progress</span><h2>${displayedRate} <span>· ${data.ledger.matches_logged}/${data.ledger.sample_gate} settled</span></h2><p>The gate is strictly above ${pct(data.ledger.hit_rate_gate)} with at least ${data.ledger.sample_gate} official results. Passing opens paper allocation and price validation only; real capital remains locked.</p><div class="progress"><span style="width:${progress}%"></span></div></article>
      <article class="ledger-panel"><span class="panel-label">Current evidence</span><div class="gate-list"><div class="gate-row"><span>Official promotion 1X2</span><span>${data.ledger.hits}/${data.ledger.matches_logged}</span></div><div class="gate-row"><span>Raw probability leader</span><span>${data.ledger.raw_probability_leader_hits}/${data.ledger.matches_logged}</span></div><div class="gate-row"><span>Latest research 1X2 · MW${latestWeek.matchweek}</span><span>${latestWeek.markets.one_x_two.hits}/${latestWeek.settled}</span></div><div class="gate-row"><span>Latest research O/U 2.5 · MW${latestWeek.matchweek}</span><span>${latestWeek.markets.over_under_2_5.hits}/${latestWeek.settled}</span></div><div class="gate-row"><span>BTTS diagnostic · zero weight</span><span>${latestWeek.markets.btts.hits}/${latestWeek.settled}</span></div><div class="gate-row"><span>Prior projected-XI accuracy</span><span>${dec(diagnostic.mean_projected_xi_hits_of_11)}/11</span></div></div></article>
    </div>
    <p class="notice">MODEL READ · Mean total xG is close, but dispersion is not: observed ${dec(environment.mean)} xG vs ${dec(forecastEnvironment.mean)} forecast, with a ${dec(environment.minimum)}–${dec(environment.maximum)} observed range versus ${dec(forecastEnvironment.minimum)}–${dec(forecastEnvironment.maximum)} forecast. ${diagnostic.structural_misses} structural reviews · ${diagnostic.process_supported_outcome_variance} result classified as finishing variance · no recalibration authorized.</p>
    <section class="section matchweek-section"><div class="section-head"><h2>Hit rate by matchweek</h2><span class="panel-label">Newest settled week opens automatically</span></div><div class="matchweek-history">${data.ledger.matchweeks.map(matchweekFold).join("")}</div></section>
    <p class="notice">Matchweek ${esc(latestWeek.matchweek)} is settled and preserved above. The next matchweek will not enter the ledger until its post-midweek data refresh is complete, its projected lineups are rebuilt, and its slate is frozen before kickoff.</p>
    <section class="section"><div class="section-head"><h2>Frozen Matchweek ${esc(data.official_slate.round)} slate</h2><span class="panel-label">${diagnostic.official_1x2_hits} hits · ${currentMisses} misses · ${currentPending} pending</span></div><div class="table-shell"><table><thead><tr><th>Fixture</th><th>Official 1X2 call</th><th>Model probability</th><th>Secondary read</th><th>Result</th></tr></thead><tbody>${slateRows}</tbody></table></div></section>`;
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
  const learning = data.methodology.research_loop;
  const adaptive = learning.adaptive;
  const challenger = adaptive.champion_challenger;
  const calibration = data.methodology.fixture_calibration;
  const chronological = calibration.chronological_audit;
  return `<section class="page-head"><p class="eyebrow">Transparent by design</p><h1>Methodology</h1><p>Simple foundations, strict chronology, and visible refusal rules. Player Quality remains locked; calibration sits downstream and cannot rewrite the intelligence after seeing a result.</p><div class="notice">ACTIVE MARKET FOCUS · 1X2 + Over/Under 2.5 · BTTS is retained only as a scored diagnostic and has zero recommendation or allocation weight</div></section>
    <div class="method-stack">
      <article class="method-card"><div class="step">01 · Intelligence</div><div><h2>Score the matchup from three foundations</h2><p>Club Form captures current attack and defence, Player Quality grades projected minutes using the locked positional Alpha formulas, and Historical Fixtures supplies a deliberately small venue and matchup residual.</p><div class="formula">fixture signal = 0.60 × club form\n               + 0.30 × projected-XI player quality\n               + 0.10 × historical residual</div></div></article>
      <article class="method-card"><div class="step">02 · Goal model</div><div><h2>Adjust the competition scoring environment</h2><p>The Premier League home and away xG baseline remains outside the composite. A separately versioned coefficient translates the normalized fixture signal into expected goals.</p><div class="formula">predicted xG = competition baseline xG × exp(β × fixture signal)</div></div></article>
      <article class="method-card holy-method"><div class="step">03 · Context</div><div><h2>Let the opponent bend the baseline</h2><p>Five attacking routes meet the opponent’s exposure and projected-XI execution. Evidence quality continuously shrinks the directional signal; archetype labels are explanatory only.</p><div class="formula">contextual xG = base xG × exp(max sensitivity × directional signal × reliability)</div></div></article>
      <article class="method-card"><div class="step">04 · Calibrate + simulate</div><div><h2>Make venue, draw and tempo evidence-dependent</h2><p>Completed frozen forecasts update a strongly shrunk league home/away xG ratio, draw-logit intercept, and total-xG environment. Team venue effects stay at zero until five home and five away observations. A draw zone creates a pass/review signal when no side separates itself.</p><div class="formula">contextual xG × venue correction × tempo correction\n        ↓ 50,000 weighted simulations\ndraw-logit correction → 1X2 + draw-risk gate</div><div class="caveats"><div class="caveat">Home/away xG ratio ${calibration.league_venue.predicted_home_away_xg_ratio.toFixed(3)} → ${calibration.adjusted_home_away_xg_ratio.toFixed(3)}</div><div class="caveat">Draw prior ${pct(calibration.draw_calibration.predicted_draw_rate)} → ${pct(calibration.draw_calibration.posterior_draw_rate)}</div><div class="caveat">Total-xG multiplier ${Math.exp(calibration.goal_environment_calibration.applied_log_total_xg_correction).toFixed(3)} · 42-day recency half-life · 30-match prior</div><div class="caveat">Cycle-forward top-pick accuracy ${pct(chronological.baseline.top_pick_accuracy)} → ${pct(chronological.calibrated.top_pick_accuracy)} · O2.5 Brier ${chronological.baseline.over_2_5_brier.toFixed(3)} → ${chronological.calibrated.over_2_5_brier.toFixed(3)}</div><div class="caveat">${calibration.training_matches}/100 matches · ${calibration.active_team_venue_modifiers} team venue effects active · shadow only</div></div></div></article>
      <article class="method-card holy-method"><div class="step">05 · Adaptive learning</div><div><h2>Diagnose every match before learning from it</h2><p>Every settled fixture becomes an immutable Match Learning Card. Result, xG process, lineup accuracy, finishing variance, and contextual execution are diagnosed separately before evidence enters fast, medium, or slow memory. Player Alpha and 60/30/10 remain locked.</p><div class="formula">freeze → observe → attribute the error\n        ↓ evidence quality + three-speed memory\nchronological challenger → human promotion gate</div><div class="caveats"><div class="caveat">${adaptive.match_learning_cards} Match Learning Cards · ${learning.completed_results}/${learning.frozen_fixtures} frozen fixtures</div><div class="caveat">Fast: lineup state · Medium: form and matchup execution · Slow: structural review</div><div class="caveat">Challenger validation: ${challenger.champion.fixtures}/${challenger.promotion_gate.minimum_validation_matches} matches · ${esc(challenger.promotion_gate.status.replaceAll("_", " "))}</div><div class="caveat">1X2 Brier improvement ${challenger.improvement_positive_is_better.one_x_two_brier === null ? "pending" : challenger.improvement_positive_is_better.one_x_two_brier.toFixed(3)} · ${learning.automatically_applied} automatically applied</div></div></div></article>
      <article class="method-card holy-method"><div class="step">06 · Decision</div><div><h2>Promote only aligned evidence</h2><p>A probability leader is not automatically a call. Strong sides need at least 55% probability and a 15-point gap. Medium sides need at least 45%, a 10-point gap, supportive context, reliable projected lineups, and both Club Form and Player Alpha pointing the same way. Draw-zone and post-midweek refresh gates can force a pass.</p><div class="formula">probability + separation + fresh XI\n+ Club Form support + Player Alpha support\n+ base/context/calibration agreement → call or pass</div><div class="caveats"><div class="caveat">1X2: &lt;45% remains a pass · draws remain review-only</div><div class="caveat">O/U 2.5: Over ≥58% · Under ≥58% · otherwise pass</div><div class="caveat">A price edge can qualify a call; it can never promote a pass</div><div class="caveat">No final slate while any projected team has a pending preleague fixture</div></div></div></article>
      <article class="method-card"><div class="step">07 · Ledger</div><div><h2>Freeze, observe, and earn the allocation review</h2><p>Forecasts are immutable. After full time, the ledger appends score, FotMob xG, lineups, closing price, and calibration metrics. A cumulative official 1X2 hit rate strictly above 50% after at least 30 fixtures opens paper allocation and price validation; it does not automatically authorize real capital.</p><div class="caveats">${data.methodology.caveats.map((item) => `<div class="caveat">${esc(item)}</div>`).join("")}</div></div></article>
    </div>`;
}

async function start() {
  const route = routeName();
  activateNav(route);
  try {
    const response = await fetch("/data/site.json", { cache: "no-store" });
    if (!response.ok) throw new Error(`Data request failed (${response.status})`);
    const data = await response.json();
    const views = { overview, predictions, ucl, "holy-grail": holyGrail, matchups, ledger, methodology };
    app.innerHTML = (views[route] || overview)(data);
    if (route === "matchups") {
      const attacker = document.querySelector("#matchup-attacker");
      const defender = document.querySelector("#matchup-defender");
      if (attacker && snapshotTeam(data.style_matchup, "Manchester City")) attacker.value = "Manchester City";
      if (defender && snapshotTeam(data.style_matchup, "Crystal Palace")) defender.value = "Crystal Palace";
      bindMatchups(data.style_matchup, data.round_robin);
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
