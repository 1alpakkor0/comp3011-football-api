import csv
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from football.models import Season, Team, Match


from datetime import datetime

def parse_date(date_str: str):
    """
    Try multiple common date formats used in football CSV datasets.
    Handles:
      - dd/mm/yy       e.g. 19/08/00
      - dd/mm/yyyy     e.g. 19/08/2021
      - yyyy-mm-dd     e.g. 2021-08-19
      - dd/mm/yyyy HH:MM:SS (if time is included)
    """
    s = date_str.strip()

    # If there's a time part (space separated), keep only date
    if " " in s:
        s = s.split(" ")[0]

    formats = ["%d/%m/%y", "%d/%m/%Y", "%Y-%m-%d"]
    for fmt in formats:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass

    raise ValueError(f"Unrecognized date format: {date_str}")


class Command(BaseCommand):
    help = "Import EPL matches from a CSV file into the database."

    def add_arguments(self, parser):
        parser.add_argument("csv_path", type=str, help="Path to the CSV file to import")
        parser.add_argument(
            "season_name",
            type=str,
            help="Season name to assign to all imported matches (e.g., 2021-2022)",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        csv_path = options["csv_path"]
        season_name = options["season_name"]

        # Create or get season
        season, _ = Season.objects.get_or_create(name=season_name)

        created_matches = 0
        skipped_matches = 0
        created_teams = 0

        try:
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)

                required_cols = {"Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG"}
                if not required_cols.issubset(reader.fieldnames or []):
                    raise CommandError(
                        f"CSV missing required columns. Found: {reader.fieldnames}"
                    )

                for row in reader:
                    # Basic cleaning
                    date_str = row["Date"].strip()
                    home_name = row["HomeTeam"].strip()
                    away_name = row["AwayTeam"].strip()
                    fthg = row["FTHG"].strip()
                    ftag = row["FTAG"].strip()

                    # Skip rows with missing scores or date
                    if not date_str or not home_name or not away_name or fthg == "" or ftag == "":
                        skipped_matches += 1
                        continue

                    match_date = parse_date(date_str)

                    # Teams
                    home_team, home_created = Team.objects.get_or_create(name=home_name)
                    away_team, away_created = Team.objects.get_or_create(name=away_name)
                    if home_created:
                        created_teams += 1
                    if away_created:
                        created_teams += 1

                    # Create match (avoid duplicates)
                    match, created = Match.objects.get_or_create(
                        season=season,
                        date=match_date,
                        home_team=home_team,
                        away_team=away_team,
                        defaults={
                            "home_score": int(fthg),
                            "away_score": int(ftag),
                        },
                    )

                    if created:
                        created_matches += 1
                    else:
                        # If it already exists, you may want to update scores (optional)
                        skipped_matches += 1

        except FileNotFoundError:
            raise CommandError(f"File not found: {csv_path}")

        self.stdout.write(self.style.SUCCESS(
            f"Import complete. Season={season_name} | Teams created={created_teams} | Matches created={created_matches} | Rows skipped={skipped_matches}"
        ))