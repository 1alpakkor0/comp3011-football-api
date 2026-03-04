from django.shortcuts import render

# Create your views here.

import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

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

@csrf_exempt
def win_probability(request):
    """
    GET /api/analytics/win-probability/?season=2021-2022&home=Arsenal&away=Chelsea&max_goals=6
    Returns probabilities for Home/Draw/Away using a Poisson goals model.
    """
    if request.method != "GET":
        return _json_error("Method not allowed", 405)

    season_name = request.GET.get("season")
    home_name = request.GET.get("home")
    away_name = request.GET.get("away")
    max_goals = request.GET.get("max_goals", "6")

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

    if season_matches.count() == 0:
        return _json_error("No matches available for this season", 400)

    # League averages for home goals and away goals per match
    total_home_goals = 0
    total_away_goals = 0
    for m in season_matches:
        total_home_goals += m.home_score
        total_away_goals += m.away_score

    n_matches = season_matches.count()
    league_home_avg = total_home_goals / n_matches
    league_away_avg = total_away_goals / n_matches

    # Team specific home attack and home defence for the home team
    home_home = season_matches.filter(home_team=home_team)
    away_away = season_matches.filter(away_team=away_team)

    # If a team has no home/away matches guard it
    if home_home.count() == 0 or away_away.count() == 0:
        return _json_error("Insufficient match data for one of the teams", 400)

    # Home team: goals scored at home and conceded at home per match
    home_scored_home = sum(m.home_score for m in home_home) / home_home.count()
    home_conceded_home = sum(m.away_score for m in home_home) / home_home.count()

    # Away team: goals scored away and conceded away per match
    away_scored_away = sum(m.away_score for m in away_away) / away_away.count()
    away_conceded_away = sum(m.home_score for m in away_away) / away_away.count()

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
    lam_home = league_home_avg * home_attack_strength * away_defence_weakness
    lam_away = league_away_avg * away_attack_strength * home_defence_weakness

    # Prevent extreme weird values
    lam_home = _clamp(lam_home, 0.1, 5.0)
    lam_away = _clamp(lam_away, 0.1, 5.0)

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

    return JsonResponse({
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
    }, status=200)
