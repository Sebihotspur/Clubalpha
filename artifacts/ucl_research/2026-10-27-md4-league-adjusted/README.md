# UCL Matchday 4 league-adjusted refresh

This is the October 27 refresh of the provisional Matchday 4 research slate.
It preserves the original cycle and adds two inputs that were previously thin:

- 286 completed current-season domestic matches across 15 leagues and 31
  foreign UCL clubs, up from 234 matches in the prior snapshot;
- the locked Player Quality v2 league-strength ladder applied once to Club
  Form after competition normalization and opponent adjustment.

Player Alpha formulas, projected-XI selection, the 60/30/10 weights, contextual
interaction and the UCL/PL calibration boundary are unchanged.

An in-memory ablation held the refreshed matches, projected XIs, Player Alpha,
Historical Fixtures and context constant, then toggled only the Club Form
league ladder. The largest ladder-only probability changes were:

- Bodø/Glimt home win versus Lille: 55.2% to 41.8%;
- Liverpool away win at Fenerbahçe: 36.4% to 47.9%, changing the leader;
- Arsenal away win at Slavia Prague: 38.9% to 50.1%;
- Real Madrid away win at AEK Athens: 40.2% to 51.6%;
- Inter away win at Feyenoord: 34.0% to 39.4%, changing the leader.

The raw side research candidates are Barcelona, Liverpool and Borussia
Dortmund. All remain unpromoted because the UCL venue, draw and tempo
calibration bucket is not yet available. Capital deployment remains disabled.
