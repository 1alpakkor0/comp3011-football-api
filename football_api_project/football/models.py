from django.db import models


class Season(models.Model):
    name = models.CharField(max_length=20, unique=True)

    def __str__(self):
        return self.name


class Team(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class Match(models.Model):
    season = models.ForeignKey(Season, on_delete=models.CASCADE)
    date = models.DateField()

    home_team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name="home_matches"
    )

    away_team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name="away_matches"
    )

    home_score = models.IntegerField()
    away_score = models.IntegerField()

    class Meta:
        unique_together = ("season", "date", "home_team", "away_team")

    def __str__(self):
        return f"{self.home_team} vs {self.away_team} ({self.date})"
