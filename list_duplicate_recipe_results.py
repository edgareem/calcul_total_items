#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Petit outil annexe pour analyser `recipes.json`.

But :
- repérer les items qui apparaissent plusieurs fois comme résultat de recette
- écrire une liste lisible dans un fichier texte

Pourquoi ce script est séparé ?
- il répond à un besoin d'audit / de diagnostic
- il ne change pas le calcul principal
- il peut être relancé indépendamment quand on veut inspecter les recettes
"""

from __future__ import annotations

import json
from pathlib import Path
from collections import Counter
from typing import Any, Dict, List, Tuple


RECIPES_FILE = Path("recipes.json")
ITEMS_FILE = Path("items.json")
OUTPUT_FILE = Path("duplicate_recipe_results.txt")


def load_json(path: Path) -> Any:
    """Lit un fichier JSON et retourne son contenu Python."""
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def build_item_name_maps(items_data: List[Dict[str, Any]]) -> Tuple[Dict[int, str], Dict[int, str]]:
    """
    Construit deux dictionnaires :
    - id -> name technique
    - id -> displayName lisible
    """
    names_by_id = {}
    display_names_by_id = {}

    for item in items_data:
        item_id = item["id"]
        names_by_id[item_id] = item["name"]
        display_names_by_id[item_id] = item.get("displayName", item["name"])

    return names_by_id, display_names_by_id


def extract_ingredients_from_recipe(recipe: Dict[str, Any]) -> Counter:
    """
    Extrait les ingredients d'une recette et retourne un Counter {item_id: qty}.

    Le format des recettes n'est pas toujours identique :
    - `inShape` pour une recette en grille
    - `ingredients` pour une liste simple
    """
    ingredients = Counter()

    if "inShape" in recipe and recipe["inShape"] is not None:
        for row in recipe["inShape"]:
            for cell in row:
                if cell is not None:
                    ingredients[int(cell)] += 1
    elif "ingredients" in recipe and recipe["ingredients"] is not None:
        for ingredient in recipe["ingredients"]:
            if ingredient is not None:
                ingredients[int(ingredient)] += 1

    return ingredients


def find_duplicate_recipe_results(
    recipes_data: Dict[str, List[Dict[str, Any]]],
    names_by_id: Dict[int, str],
    display_names_by_id: Dict[int, str],
) -> List[Dict[str, Any]]:
    """
    Cherche tous les items qui ont plusieurs recettes pour le même résultat.

    Ici, on considère qu'un item est "dupliqué en résultat" si la liste
    associée à sa clé dans `recipes.json` contient plus d'une recette.
    """
    duplicates = []

    for result_id_str, recipe_list in recipes_data.items():
        if not isinstance(recipe_list, list) or len(recipe_list) <= 1:
            continue

        try:
            result_id = int(result_id_str)
        except ValueError:
            continue

        duplicates.append(
            {
                "result_id": result_id,
                "name": names_by_id.get(result_id, f"unknown_{result_id}"),
                "display_name": display_names_by_id.get(result_id, f"unknown_{result_id}"),
                "recipe_count": len(recipe_list),
                "recipes": recipe_list,
            }
        )

    duplicates.sort(key=lambda entry: (entry["display_name"].lower(), entry["name"]))
    return duplicates


def write_duplicate_results_report(
    duplicates: List[Dict[str, Any]],
    names_by_id: Dict[int, str],
    output_path: Path,
) -> None:
    """
    Ecrit un rapport texte detaille.

    Pour chaque item ayant plusieurs recettes, on liste chaque craft avec :
    - un numero de craft
    - la quantite produite
    - les ingredients et leurs quantites

    Ce format servira plus tard a choisir explicitement un craft a conserver.
    """
    lines = []
    lines.append("=== ITEMS AVEC PLUSIEURS RECETTES POUR LE MEME RESULTAT ===")
    lines.append(f"Total : {len(duplicates)}")
    lines.append("")

    for entry in duplicates:
        lines.append(
            f"- {entry['display_name']} ({entry['name']}, id={entry['result_id']}) -> {entry['recipe_count']} recettes"
        )
        for recipe_index, recipe in enumerate(entry["recipes"], start=1):
            result = recipe.get("result", {})
            result_count = int(result.get("count", 1))
            lines.append(f"    craft {recipe_index}:")
            lines.append(f"    produit: x{result_count}")

            ingredients = extract_ingredients_from_recipe(recipe)
            if not ingredients:
                lines.append("    ingredients: (aucun ingredient detecte)")
                continue

            for ingredient_id, qty in sorted(ingredients.items(), key=lambda kv: names_by_id.get(kv[0], str(kv[0]))):
                ingredient_name = names_by_id.get(ingredient_id, f"unknown_{ingredient_id}")
                lines.append(f"    - {ingredient_name} x{qty}")
        lines.append("")

    with output_path.open("w", encoding="utf-8") as file:
        file.write("\n".join(lines))


def main() -> None:
    """Point d'entrée du script."""
    if not RECIPES_FILE.exists():
        raise FileNotFoundError(f"Fichier introuvable: {RECIPES_FILE}")
    if not ITEMS_FILE.exists():
        raise FileNotFoundError(f"Fichier introuvable: {ITEMS_FILE}")

    print(f"[Init] Chargement de {ITEMS_FILE}...")
    items_data = load_json(ITEMS_FILE)
    print(f"[Init] Chargement de {RECIPES_FILE}...")
    recipes_data = load_json(RECIPES_FILE)

    names_by_id, display_names_by_id = build_item_name_maps(items_data)
    duplicates = find_duplicate_recipe_results(recipes_data, names_by_id, display_names_by_id)
    write_duplicate_results_report(duplicates, names_by_id, OUTPUT_FILE)

    print(f"[Termine] Rapport cree : {OUTPUT_FILE}")
    print(f"[Termine] Items avec plusieurs recettes : {len(duplicates)}")


if __name__ == "__main__":
    main()
