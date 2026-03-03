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
