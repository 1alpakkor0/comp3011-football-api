from django.shortcuts import render

# Create your views here.

import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse

from .models import Team, Match, Season


def _json_error(message: str, status: int):
    return JsonResponse({"error": message}, status=status)


def _parse_json_body(request):
    try:
        if not request.body:
            return None, _json_error("Empty request body", 400)
        data = json.loads(request.body.decode("utf-8"))
        if not isinstance(data, dict):
            return None, _json_error("JSON body must be an object", 400)
        return data, None
    except json.JSONDecodeError:
        return None, _json_error("Invalid JSON", 400)



# teams for GET and POST

@csrf_exempt
def teams_collection(request):
    """
    GET  /api/teams/?search=ars
    POST /api/teams/   body: {"name":"Arsenal"}
    """
    if request.method == "GET":
        search = request.GET.get("search")
        qs = Team.objects.all().order_by("name")
        if search:
            qs = qs.filter(name__icontains=search)

        teams = list(qs.values("id", "name"))
        return JsonResponse({"count": len(teams), "teams": teams}, status=200)

    if request.method == "POST":
        data, err = _parse_json_body(request)
        if err:
            return err

        name = (data.get("name") or "").strip()
        if not name:
            return _json_error("Field 'name' is required", 400)

        if Team.objects.filter(name=name).exists():
            return _json_error("Team already exists", 409)

        team = Team.objects.create(name=name)
        return JsonResponse({"id": team.id, "name": team.name}, status=201)

    return _json_error("Method not allowed", 405)


@csrf_exempt
def team_item(request, team_id: int):
    """
    GET    /api/teams/<id>/
    PUT    /api/teams/<id>/   body: {"name":"New Name"}
    DELETE /api/teams/<id>/
    """
    try:
        team = Team.objects.get(id=team_id)
    except Team.DoesNotExist:
        return _json_error("Team not found", 404)

    if request.method == "GET":
        return JsonResponse({"id": team.id, "name": team.name}, status=200)

    if request.method == "PUT":
        data, err = _parse_json_body(request)
        if err:
            return err

        name = (data.get("name") or "").strip()
        if not name:
            return _json_error("Field 'name' is required", 400)

        if Team.objects.filter(name=name).exclude(id=team.id).exists():
            return _json_error("Team name already exists", 409)

        team.name = name
        team.save()
        return JsonResponse({"id": team.id, "name": team.name}, status=200)

    if request.method == "DELETE":
        team.delete()
        return JsonResponse({}, status=204)

    return _json_error("Method not allowed", 405)



# matches for GET only for now

@csrf_exempt
def matches_collection(request):
    """
    GET /api/matches/?season=2021-2022&team=Arsenal
    """
    if request.method != "GET":
        return _json_error("Method not allowed", 405)

    season_name = request.GET.get("season")  
    team = request.GET.get("team")          # substring match on team name

    qs = Match.objects.select_related("season", "home_team", "away_team").all()

    if season_name:
        qs = qs.filter(season__name=season_name)

    if team:
        qs = qs.filter(home_team__name__icontains=team) | qs.filter(away_team__name__icontains=team)

    qs = qs.order_by("date")

    matches = []
    for m in qs[:500]:  # safety limit
        matches.append({
            "id": m.id,
            "season": m.season.name,
            "date": str(m.date),
            "home_team": m.home_team.name,
            "away_team": m.away_team.name,
            "home_score": m.home_score,
            "away_score": m.away_score,
        })

    return JsonResponse({"count": len(matches), "matches": matches}, status=200)


@csrf_exempt
def league_table(request):
    """
    GET /api/analytics/table/?season=2021-2022
    Computes league standings from Match rows for that season.
    Points: Win=3, Draw=1, Loss=0
    Sorting: points desc, gd desc, gf desc, name asc
    """
    if request.method != "GET":
        return _json_error("Method not allowed", 405)

    season_name = request.GET.get("season")
    if not season_name:
        return _json_error("Query parameter 'season' is required (e.g. season=2021-2022)", 400)

    # validate season exists
    try:
        season = Season.objects.get(name=season_name)
    except Season.DoesNotExist:
        return _json_error("Season not found", 404)

    matches = Match.objects.select_related("home_team", "away_team").filter(season=season)

    # Initialize stats for every team seen in this season
    team_stats = {}

    def ensure_team(team):
        if team.id not in team_stats:
            team_stats[team.id] = {
                "team_id": team.id,
                "team": team.name,
                "played": 0,
                "wins": 0,
                "draws": 0,
                "losses": 0,
                "gf": 0,
                "ga": 0,
                "gd": 0,
                "points": 0,
            }

    for m in matches:
        home = m.home_team
        away = m.away_team
        ensure_team(home)
        ensure_team(away)

        hs = m.home_score
        as_ = m.away_score

        team_stats[home.id]["played"] += 1
        team_stats[away.id]["played"] += 1

        team_stats[home.id]["gf"] += hs
        team_stats[home.id]["ga"] += as_

        team_stats[away.id]["gf"] += as_
        team_stats[away.id]["ga"] += hs

        if hs > as_:
            team_stats[home.id]["wins"] += 1
            team_stats[away.id]["losses"] += 1
            team_stats[home.id]["points"] += 3
        elif hs < as_:
            team_stats[away.id]["wins"] += 1
            team_stats[home.id]["losses"] += 1
            team_stats[away.id]["points"] += 3
        else:
            team_stats[home.id]["draws"] += 1
            team_stats[away.id]["draws"] += 1
            team_stats[home.id]["points"] += 1
            team_stats[away.id]["points"] += 1

    # goal difference
    for tid in team_stats:
        team_stats[tid]["gd"] = team_stats[tid]["gf"] - team_stats[tid]["ga"]

    rows = list(team_stats.values())
    rows.sort(key=lambda r: (-r["points"], -r["gd"], -r["gf"], r["team"]))

    # add rank
    for i, r in enumerate(rows, start=1):
        r["position"] = i

    return JsonResponse(
        {"season": season.name, "teams": len(rows), "table": rows},
        status=200
    )


@csrf_exempt
def performance_summary(request):
    """
    GET /api/analytics/performance/?season=2021-2022&team=Arsenal&last=5
    """
    if request.method != "GET":
        return _json_error("Method not allowed", 405)

    season_name = request.GET.get("season")
    team_name = request.GET.get("team")
    last_n = request.GET.get("last", "5")

    if not season_name:
        return _json_error("Query parameter 'season' is required", 400)
    if not team_name:
        return _json_error("Query parameter 'team' is required", 400)

    try:
        last_n = int(last_n)
        if last_n < 1 or last_n > 20:
            return _json_error("'last' must be between 1 and 20", 400)
    except ValueError:
        return _json_error("'last' must be an integer", 400)

    try:
        season = Season.objects.get(name=season_name)
    except Season.DoesNotExist:
        return _json_error("Season not found", 404)

    # Find team by case insensitive match
    try:
        team = Team.objects.get(name__iexact=team_name)
    except Team.DoesNotExist:
        return _json_error("Team not found", 404)

    matches = (
        Match.objects
        .select_related("home_team", "away_team")
        .filter(season=season)
        .filter(home_team=team) | Match.objects.select_related("home_team", "away_team").filter(season=season).filter(away_team=team)
    )
    matches = matches.order_by("date", "id")

    if matches.count() == 0:
        return JsonResponse({
            "season": season.name,
            "team": team.name,
            "message": "No matches found for this team in this season."
        }, status=200)

    def result_for_team(m):
        # returns w,d,l from this teams perspective
        if m.home_team_id == team.id:
            gf, ga = m.home_score, m.away_score
        else:
            gf, ga = m.away_score, m.home_score

        if gf > ga:
            return "W"
        if gf < ga:
            return "L"
        return "D"

    # overall stats
    stats = {
        "played": 0, "wins": 0, "draws": 0, "losses": 0,
        "gf": 0, "ga": 0, "gd": 0, "points": 0,
        "clean_sheets": 0,
        "home": {"played": 0, "wins": 0, "draws": 0, "losses": 0, "gf": 0, "ga": 0, "points": 0},
        "away": {"played": 0, "wins": 0, "draws": 0, "losses": 0, "gf": 0, "ga": 0, "points": 0},
        "biggest_win": None,   # by goal difference
        "biggest_loss": None,  # by negative goal difference
    }

    form = []
    current_streak = {"type": None, "count": 0}

    for m in matches:
        stats["played"] += 1
        is_home = (m.home_team_id == team.id)

        if is_home:
            gf, ga = m.home_score, m.away_score
            bucket = stats["home"]
        else:
            gf, ga = m.away_score, m.home_score
            bucket = stats["away"]

        stats["gf"] += gf
        stats["ga"] += ga
        bucket["played"] += 1
        bucket["gf"] += gf
        bucket["ga"] += ga

        if ga == 0:
            stats["clean_sheets"] += 1

        r = "D"
        pts = 1
        if gf > ga:
            r, pts = "W", 3
        elif gf < ga:
            r, pts = "L", 0

        if r == "W":
            stats["wins"] += 1
            bucket["wins"] += 1
        elif r == "L":
            stats["losses"] += 1
            bucket["losses"] += 1
        else:
            stats["draws"] += 1
            bucket["draws"] += 1

        stats["points"] += pts
        bucket["points"] += pts

        # biggest win and loss
        gd = gf - ga
        entry = {
            "date": str(m.date),
            "home_team": m.home_team.name,
            "away_team": m.away_team.name,
            "score": f"{m.home_score}-{m.away_score}",
            "team_result": r,
            "team_gd": gd,
        }
        if stats["biggest_win"] is None or gd > stats["biggest_win"]["team_gd"]:
            stats["biggest_win"] = entry
        if stats["biggest_loss"] is None or gd < stats["biggest_loss"]["team_gd"]:
            stats["biggest_loss"] = entry

        # streak
        if current_streak["type"] is None or current_streak["type"] == r:
            current_streak["type"] = r
            current_streak["count"] += 1
        else:
            current_streak = {"type": r, "count": 1}

        form.append(r)

    stats["gd"] = stats["gf"] - stats["ga"]
    stats["home"]["gd"] = stats["home"]["gf"] - stats["home"]["ga"]
    stats["away"]["gd"] = stats["away"]["gf"] - stats["away"]["ga"]

    last_form = form[-last_n:]

    return JsonResponse({
        "season": season.name,
        "team": team.name,
        "overall": stats,
        "current_streak": current_streak,
        "form_last_n": {"n": last_n, "sequence": last_form},
    }, status=200)




import math

def _poisson_pmf(k: int, lam: float) -> float:
    return (math.exp(-lam) * (lam ** k)) / math.factorial(k)

def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def _compute_poisson_win_probs(season_matches, league_home_avg, league_away_avg, home_team, away_team, max_goals):
    """
    Returns: (lam_home, lam_away, p_home_win, p_draw, p_away_win)
    Uses the same logic as win_probability.
    """
    home_home = season_matches.filter(home_team=home_team)
    away_away = season_matches.filter(away_team=away_team)

    home_home_n = home_home.count()
    away_away_n = away_away.count()
    if home_home_n == 0 or away_away_n == 0:
        return None  # insufficient data

    home_scored_home = sum(m.home_score for m in home_home) / home_home_n
    home_conceded_home = sum(m.away_score for m in home_home) / home_home_n

    away_scored_away = sum(m.away_score for m in away_away) / away_away_n
    away_conceded_away = sum(m.home_score for m in away_away) / away_away_n

    home_attack_strength = home_scored_home / league_home_avg if league_home_avg > 0 else 1.0
    away_defence_weakness = away_conceded_away / league_home_avg if league_home_avg > 0 else 1.0

    away_attack_strength = away_scored_away / league_away_avg if league_away_avg > 0 else 1.0
    home_defence_weakness = home_conceded_home / league_away_avg if league_away_avg > 0 else 1.0

    raw_lam_home = league_home_avg * home_attack_strength * away_defence_weakness
    raw_lam_away = league_away_avg * away_attack_strength * home_defence_weakness

    lam_home = _clamp(raw_lam_home, 0.1, 5.0)
    lam_away = _clamp(raw_lam_away, 0.1, 5.0)

    p_home_win = 0.0
    p_draw = 0.0
    p_away_win = 0.0

    for hg in range(0, max_goals + 1):
        p_hg = _poisson_pmf(hg, lam_home)
        for ag in range(0, max_goals + 1):
            p_ag = _poisson_pmf(ag, lam_away)
            p = p_hg * p_ag
            if hg > ag:
                p_home_win += p
            elif hg == ag:
                p_draw += p
            else:
                p_away_win += p

    total = p_home_win + p_draw + p_away_win
    if total > 0:
        p_home_win /= total
        p_draw /= total
        p_away_win /= total

    return (lam_home, lam_away, p_home_win, p_draw, p_away_win)




@csrf_exempt
def win_probability(request):
    """
    GET /api/analytics/win-probability/?season=2021-2022&home=Arsenal&away=Chelsea&max_goals=6&explain=1
    Returns probabilities for Home/Draw/Away using a Poisson goals model.
    If explain=1, also returns intermediate stats used to compute lambdas.
    """
    if request.method != "GET":
        return _json_error("Method not allowed", 405)

    season_name = request.GET.get("season")
    home_name = request.GET.get("home")
    away_name = request.GET.get("away")
    max_goals = request.GET.get("max_goals", "6")
    explain = request.GET.get("explain", "0") == "1"

    if not season_name:
        return _json_error("Query parameter 'season' is required", 400)
    if not home_name or not away_name:
        return _json_error("Query parameters 'home' and 'away' are required", 400)

    try:
        max_goals = int(max_goals)
        if max_goals < 3 or max_goals > 10:
            return _json_error("'max_goals' must be between 3 and 10", 400)
    except ValueError:
        return _json_error("'max_goals' must be an integer", 400)

    try:
        season = Season.objects.get(name=season_name)
    except Season.DoesNotExist:
        return _json_error("Season not found", 404)

    try:
        home_team = Team.objects.get(name__iexact=home_name)
        away_team = Team.objects.get(name__iexact=away_name)
    except Team.DoesNotExist:
        return _json_error("Home or away team not found", 404)

    # Pull all matches for the season
    season_matches = Match.objects.select_related("home_team", "away_team").filter(season=season)

    n_matches = season_matches.count()
    if n_matches == 0:
        return _json_error("No matches available for this season", 400)

    # League averages for home goals and away goals per match
    total_home_goals = 0
    total_away_goals = 0
    for m in season_matches:
        total_home_goals += m.home_score
        total_away_goals += m.away_score

    league_home_avg = total_home_goals / n_matches
    league_away_avg = total_away_goals / n_matches

    # Team specific home attack and home defence for the home team
    home_home = season_matches.filter(home_team=home_team)
    away_away = season_matches.filter(away_team=away_team)

    home_home_n = home_home.count()
    away_away_n = away_away.count()

    # If a team has no home/away matches guard it
    if home_home_n == 0 or away_away_n == 0:
        return _json_error("Insufficient match data for one of the teams", 400)

    # Home team: goals scored at home and conceded at home per match
    home_scored_home = sum(m.home_score for m in home_home) / home_home_n
    home_conceded_home = sum(m.away_score for m in home_home) / home_home_n

    # Away team: goals scored away and conceded away per match
    away_scored_away = sum(m.away_score for m in away_away) / away_away_n
    away_conceded_away = sum(m.home_score for m in away_away) / away_away_n

    # Strength ratios relative to league averages
    # attack_strength > 1 means above average scoring
    # defence_weakness > 1 means concede more than average
    home_attack_strength = home_scored_home / league_home_avg if league_home_avg > 0 else 1.0
    away_defence_weakness = away_conceded_away / league_home_avg if league_home_avg > 0 else 1.0

    away_attack_strength = away_scored_away / league_away_avg if league_away_avg > 0 else 1.0
    home_defence_weakness = home_conceded_home / league_away_avg if league_away_avg > 0 else 1.0

    # Expected goals lambdas
    # Home expected goals depends on league_home_avg * home_attack_strength * away_defence_weakness
    # Away expected goals depends on league_away_avg * away_attack_strength * home_defence_weakness
    raw_lam_home = league_home_avg * home_attack_strength * away_defence_weakness
    raw_lam_away = league_away_avg * away_attack_strength * home_defence_weakness

    # Prevent extreme weird values
    lam_home = _clamp(raw_lam_home, 0.1, 5.0)
    lam_away = _clamp(raw_lam_away, 0.1, 5.0)

    # Scoreline probabilities (0..max_goals)
    p_home_win = 0.0
    p_draw = 0.0
    p_away_win = 0.0

    for hg in range(0, max_goals + 1):
        p_hg = _poisson_pmf(hg, lam_home)
        for ag in range(0, max_goals + 1):
            p_ag = _poisson_pmf(ag, lam_away)
            p = p_hg * p_ag
            if hg > ag:
                p_home_win += p
            elif hg == ag:
                p_draw += p
            else:
                p_away_win += p

    # Normalising because we truncated at max_goals
    total = p_home_win + p_draw + p_away_win
    if total > 0:
        p_home_win /= total
        p_draw /= total
        p_away_win /= total

    resp = {
        "season": season.name,
        "home": home_team.name,
        "away": away_team.name,
        "model": {
            "type": "poisson",
            "max_goals": max_goals,
            "league_home_avg": round(league_home_avg, 4),
            "league_away_avg": round(league_away_avg, 4),
            "lambda_home": round(lam_home, 4),
            "lambda_away": round(lam_away, 4),
        },
        "probabilities": {
            "home_win": round(p_home_win, 4),
            "draw": round(p_draw, 4),
            "away_win": round(p_away_win, 4),
        }
    }

    if explain:
        resp["explain"] = {
            "league": {
                "matches_used": n_matches,
                "home_avg_goals_per_match": round(league_home_avg, 4),
                "away_avg_goals_per_match": round(league_away_avg, 4),
            },
            "home_team_home_matches": {
                "team": home_team.name,
                "matches": home_home_n,
                "scored_per_match": round(home_scored_home, 4),
                "conceded_per_match": round(home_conceded_home, 4),
                "attack_strength_vs_league_home": round(home_attack_strength, 4),
                "defence_weakness_vs_league_away": round(home_defence_weakness, 4),
            },
            "away_team_away_matches": {
                "team": away_team.name,
                "matches": away_away_n,
                "scored_per_match": round(away_scored_away, 4),
                "conceded_per_match": round(away_conceded_away, 4),
                "attack_strength_vs_league_away": round(away_attack_strength, 4),
                "defence_weakness_vs_league_home": round(away_defence_weakness, 4),
            },
            "expected_goals": {
                "raw_lambda_home": round(raw_lam_home, 4),
                "raw_lambda_away": round(raw_lam_away, 4),
                "lambda_home_clamped": round(lam_home, 4),
                "lambda_away_clamped": round(lam_away, 4),
                "clamp_range": {"min": 0.1, "max": 5.0},
                "note": "Lambdas are computed from league averages scaled by attack/defence ratios, then clamped for stability.",
            },
        }

    return JsonResponse(resp, status=200)


@csrf_exempt
def win_probability_batch(request):
    """
    GET /api/analytics/win-probability/batch/?season=2021-2022&team=Arsenal&venue=home&max_goals=6
    venue: home | away | both
    Returns probabilities vs every opponent team in that season.
    """
    if request.method != "GET":
        return _json_error("Method not allowed", 405)

    season_name = request.GET.get("season")
    team_name = request.GET.get("team") or request.GET.get("home")  # allow home alias
    venue = (request.GET.get("venue") or "home").lower()
    max_goals = request.GET.get("max_goals", "6")

    if not season_name:
        return _json_error("Query parameter 'season' is required", 400)
    if not team_name:
        return _json_error("Query parameter 'team' is required (or use 'home' as alias)", 400)

    if venue not in {"home", "away", "both"}:
        return _json_error("Query parameter 'venue' must be one of: home, away, both", 400)

    try:
        max_goals = int(max_goals)
        if max_goals < 3 or max_goals > 10:
            return _json_error("'max_goals' must be between 3 and 10", 400)
    except ValueError:
        return _json_error("'max_goals' must be an integer", 400)

    try:
        season = Season.objects.get(name=season_name)
    except Season.DoesNotExist:
        return _json_error("Season not found", 404)

    try:
        base_team = Team.objects.get(name__iexact=team_name)
    except Team.DoesNotExist:
        return _json_error("Team not found", 404)

    season_matches = Match.objects.select_related("home_team", "away_team").filter(season=season)
    n_matches = season_matches.count()
    if n_matches == 0:
        return _json_error("No matches available for this season", 400)

    # league averages
    total_home_goals = sum(m.home_score for m in season_matches)
    total_away_goals = sum(m.away_score for m in season_matches)
    league_home_avg = total_home_goals / n_matches
    league_away_avg = total_away_goals / n_matches

    # Finding opponents for all teams that played in the season excluding base_team
    team_ids = set()
    for m in season_matches:
        team_ids.add(m.home_team_id)
        team_ids.add(m.away_team_id)

    opponents = Team.objects.filter(id__in=team_ids).exclude(id=base_team.id).order_by("name")

    results = []

    def pack(home_team, away_team):
        out = _compute_poisson_win_probs(
            season_matches=season_matches,
            league_home_avg=league_home_avg,
            league_away_avg=league_away_avg,
            home_team=home_team,
            away_team=away_team,
            max_goals=max_goals
        )
        if out is None:
            return None
        lam_h, lam_a, p_h, p_d, p_a = out
        return {
            "home": home_team.name,
            "away": away_team.name,
            "lambda_home": round(lam_h, 4),
            "lambda_away": round(lam_a, 4),
            "probabilities": {
                "home_win": round(p_h, 4),
                "draw": round(p_d, 4),
                "away_win": round(p_a, 4),
            }
        }

    for opp in opponents:
        if venue == "home":
            row = pack(base_team, opp)
            if row:
                results.append(row)
        elif venue == "away":
            row = pack(opp, base_team)
            if row:
                results.append(row)
        else:  # both
            row_home = pack(base_team, opp)
            row_away = pack(opp, base_team)
            if row_home or row_away:
                results.append({
                    "opponent": opp.name,
                    "as_home": row_home,
                    "as_away": row_away
                })

    return JsonResponse({
        "season": season.name,
        "team": base_team.name,
        "venue": venue,
        "model": {
            "type": "poisson",
            "max_goals": max_goals,
            "league_home_avg": round(league_home_avg, 4),
            "league_away_avg": round(league_away_avg, 4),
            "matches_used": n_matches
        },
        "count": len(results),
        "results": results
    }, status=200)



@csrf_exempt
def predict_table(request):
    """
    GET /api/analytics/predict-table/?season=2021-2022&max_goals=6

    Produces an expected league table by replacing each match outcome
    with Poisson-based expected points: xPts_home = 3*P for home_win + 1*P for draw and xPts_away = 3*Pfor away_win + 1*P fordraw
      
      

    Also aggregates expected goals using lambdas (xGF/xGA/xGD).
    """
    if request.method != "GET":
        return _json_error("Method not allowed", 405)

    season_name = request.GET.get("season")
    max_goals = request.GET.get("max_goals", "6")

    if not season_name:
        return _json_error("Query parameter 'season' is required (e.g. season=2021-2022)", 400)

    try:
        max_goals = int(max_goals)
        if max_goals < 3 or max_goals > 10:
            return _json_error("'max_goals' must be between 3 and 10", 400)
    except ValueError:
        return _json_error("'max_goals' must be an integer", 400)

    try:
        season = Season.objects.get(name=season_name)
    except Season.DoesNotExist:
        return _json_error("Season not found", 404)

    matches = (
        Match.objects
        .select_related("home_team", "away_team")
        .filter(season=season)
        .order_by("date", "id")
    )

    n_matches = matches.count()
    if n_matches == 0:
        return _json_error("No matches available for this season", 400)

    
    # League averages
    
    total_home_goals = 0
    total_away_goals = 0

    # Also gather team ids in this season
    team_ids = set()

    for m in matches:
        total_home_goals += m.home_score
        total_away_goals += m.away_score
        team_ids.add(m.home_team_id)
        team_ids.add(m.away_team_id)

    league_home_avg = total_home_goals / n_matches
    league_away_avg = total_away_goals / n_matches

    # Precompute per team home and away scoring rates so we do not have to filter every single data

    home_stats = {}
    away_stats = {}

    def ensure(stats_dict, tid):
        if tid not in stats_dict:
            stats_dict[tid] = {"n": 0, "scored": 0, "conceded": 0}

    for m in matches:
        ensure(home_stats, m.home_team_id)
        ensure(away_stats, m.away_team_id)

        home_stats[m.home_team_id]["n"] += 1
        home_stats[m.home_team_id]["scored"] += m.home_score
        home_stats[m.home_team_id]["conceded"] += m.away_score

        away_stats[m.away_team_id]["n"] += 1
        away_stats[m.away_team_id]["scored"] += m.away_score
        away_stats[m.away_team_id]["conceded"] += m.home_score

  
    # Initialise expected table rows

    teams = Team.objects.filter(id__in=team_ids)
    x = {}
    for t in teams:
        x[t.id] = {
            "team_id": t.id,
            "team": t.name,
            "played": 0,
            "xpoints": 0.0,
            "xgf": 0.0,
            "xga": 0.0,
            "xgd": 0.0,
        }


    # For each match computing poisson probs + expected points

    for m in matches:
        hid = m.home_team_id
        aid = m.away_team_id

        if hid not in home_stats or aid not in away_stats:
            continue

        # Home team rates in home games
        hh = home_stats[hid]
        # Away team rates in away games
        aa = away_stats[aid]

        # per match averages
        home_scored_home = hh["scored"] / hh["n"]
        home_conceded_home = hh["conceded"] / hh["n"]

        away_scored_away = aa["scored"] / aa["n"]
        away_conceded_away = aa["conceded"] / aa["n"]

        # strength ratios relative to league averages
        home_attack_strength = home_scored_home / league_home_avg if league_home_avg > 0 else 1.0
        away_defence_weakness = away_conceded_away / league_home_avg if league_home_avg > 0 else 1.0

        away_attack_strength = away_scored_away / league_away_avg if league_away_avg > 0 else 1.0
        home_defence_weakness = home_conceded_home / league_away_avg if league_away_avg > 0 else 1.0

        # expected goals
        lam_home = _clamp(league_home_avg * home_attack_strength * away_defence_weakness, 0.1, 5.0)
        lam_away = _clamp(league_away_avg * away_attack_strength * home_defence_weakness, 0.1, 5.0)

        # probs from Poisson (0..max_goals)
        p_home_win = 0.0
        p_draw = 0.0
        p_away_win = 0.0

        for hg in range(0, max_goals + 1):
            p_hg = _poisson_pmf(hg, lam_home)
            for ag in range(0, max_goals + 1):
                p_ag = _poisson_pmf(ag, lam_away)
                p = p_hg * p_ag
                if hg > ag:
                    p_home_win += p
                elif hg == ag:
                    p_draw += p
                else:
                    p_away_win += p

        # normalising
        total = p_home_win + p_draw + p_away_win
        if total > 0:
            p_home_win /= total
            p_draw /= total
            p_away_win /= total

        # expected points for this match
        xpts_home = 3.0 * p_home_win + 1.0 * p_draw
        xpts_away = 3.0 * p_away_win + 1.0 * p_draw

        # aggregate
        x[hid]["played"] += 1
        x[aid]["played"] += 1

        x[hid]["xpoints"] += xpts_home
        x[aid]["xpoints"] += xpts_away

        # expected goals using lambdas
        x[hid]["xgf"] += lam_home
        x[hid]["xga"] += lam_away

        x[aid]["xgf"] += lam_away
        x[aid]["xga"] += lam_home

    # finish xgd and rounding
    rows = []
    for tid, r in x.items():
        r["xgd"] = r["xgf"] - r["xga"]

        
        r["xpoints"] = round(r["xpoints"], 3)
        r["xgf"] = round(r["xgf"], 3)
        r["xga"] = round(r["xga"], 3)
        r["xgd"] = round(r["xgd"], 3)

        rows.append(r)

    # sort like a league xpoints desc, xgd desc, xgf desc, name asc
    rows.sort(key=lambda r: (-r["xpoints"], -r["xgd"], -r["xgf"], r["team"]))

    for i, r in enumerate(rows, start=1):
        r["position"] = i

    return JsonResponse({
        "season": season.name,
        "model": {
            "type": "poisson_expected_points",
            "max_goals": max_goals,
            "league_home_avg": round(league_home_avg, 4),
            "league_away_avg": round(league_away_avg, 4),
            "matches_used": n_matches
        },
        "teams": len(rows),
        "table": rows
    }, status=200)



def dashboard(request):
    html = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>COMP3011 Football API Dashboard</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 24px; }
    h1 { margin-bottom: 8px; }
    .row { display: flex; gap: 12px; flex-wrap: wrap; align-items: center; }
    select, input, button { padding: 8px 10px; font-size: 14px; }
    button { cursor: pointer; }
    .card { border: 1px solid #ddd; border-radius: 10px; padding: 16px; margin-top: 16px; }
    table { border-collapse: collapse; width: 100%; margin-top: 12px; }
    th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
    th { background: #f6f6f6; }
    .muted { color: #666; font-size: 13px; }
    .pill { display:inline-block; padding:2px 8px; border-radius: 999px; background:#eee; font-size:12px; }
    .grid { display:grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 12px; margin-top: 12px; }
  </style>
</head>
<body>
  <h1>Football Analytics Dashboard</h1>
  <div class="muted">Uses your live API endpoints (league table, expected table, win probability).</div>

  <div class="card">
    <div class="row">
      <label>Season:</label>
      <select id="season">
        <option value="2021-2022">2021-2022</option>
        <option value="2020-2021">2020-2021</option>
      </select>

      <button onclick="loadTable()">League Table</button>
      <button onclick="loadXTable()">xPoints Table</button>
    </div>
  </div>

  <div class="card">
    <div class="row">
      <span class="pill">Win Probability</span>
      <label>Home:</label>
      <input id="home" value="Arsenal"/>
      <label>Away:</label>
      <input id="away" value="Chelsea"/>
      <button onclick="loadWinProb()">Compute</button>
    </div>
    <div id="winprob" class="grid"></div>
  </div>

  <div class="card">
    <div id="outputTitle" class="pill">Output</div>
    <div id="output"></div>
  </div>

<script>
function renderTable(rows, columns, title) {
  document.getElementById("outputTitle").textContent = title;
  const out = document.getElementById("output");

  let html = "<table><thead><tr>";
  for (const c of columns) html += `<th>${c.header}</th>`;
  html += "</tr></thead><tbody>";

  for (const r of rows) {
    html += "<tr>";
    for (const c of columns) html += `<td>${r[c.key]}</td>`;
    html += "</tr>";
  }
  html += "</tbody></table>";
  out.innerHTML = html;
}

async function loadTable() {
  const season = document.getElementById("season").value;
  const res = await fetch(`/api/analytics/table/?season=${encodeURIComponent(season)}`);
  const data = await res.json();
  const cols = [
    {key:"position", header:"#"},
    {key:"team", header:"Team"},
    {key:"played", header:"P"},
    {key:"wins", header:"W"},
    {key:"draws", header:"D"},
    {key:"losses", header:"L"},
    {key:"gf", header:"GF"},
    {key:"ga", header:"GA"},
    {key:"gd", header:"GD"},
    {key:"points", header:"Pts"},
  ];
  renderTable(data.table, cols, `League Table (${data.season})`);
}

async function loadXTable() {
  const season = document.getElementById("season").value;
  const res = await fetch(`/api/analytics/predict-table/?season=${encodeURIComponent(season)}`);
  const data = await res.json();
  const cols = [
    {key:"position", header:"#"},
    {key:"team", header:"Team"},
    {key:"played", header:"P"},
    {key:"xpoints", header:"xPts"},
    {key:"xgf", header:"xGF"},
    {key:"xga", header:"xGA"},
    {key:"xgd", header:"xGD"},
  ];
  renderTable(data.table, cols, `xPoints Table (${data.season})`);
}

function renderWinProb(data) {
  const wp = document.getElementById("winprob");
  wp.innerHTML = `
    <div class="card"><div class="pill">Model</div>
      <div class="muted">λ_home: <b>${data.model.lambda_home}</b>, λ_away: <b>${data.model.lambda_away}</b></div>
      <div class="muted">League avgs: home <b>${data.model.league_home_avg}</b>, away <b>${data.model.league_away_avg}</b></div>
    </div>
    <div class="card"><div class="pill">Probabilities</div>
      <div>Home win: <b>${data.probabilities.home_win}</b></div>
      <div>Draw: <b>${data.probabilities.draw}</b></div>
      <div>Away win: <b>${data.probabilities.away_win}</b></div>
    </div>
  `;
}

async function loadWinProb() {
  const season = document.getElementById("season").value;
  const home = document.getElementById("home").value;
  const away = document.getElementById("away").value;

  const url = `/api/analytics/win-probability/?season=${encodeURIComponent(season)}&home=${encodeURIComponent(home)}&away=${encodeURIComponent(away)}`;
  const res = await fetch(url);
  const data = await res.json();

  if (data.error) {
    document.getElementById("winprob").innerHTML = `<div class="card"><b>Error:</b> ${data.error}</div>`;
    return;
  }
  renderWinProb(data);
}
</script>
</body>
</html>
"""
    return HttpResponse(html)