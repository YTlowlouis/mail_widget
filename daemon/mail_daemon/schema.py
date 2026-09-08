"""Schéma strict de la sortie du modèle. Toute valeur hors schéma est rejetée, jamais interprétée."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Urgence = Literal["action", "info", "bruit"]


class EmailClassification(BaseModel):
    resume: str = Field(description="Résumé en une phrase, remplace le sujet à l'affichage, ne le paraphrase pas")
    urgence: Urgence
    raison: str = Field(description="Courte justification du niveau d'urgence choisi")
