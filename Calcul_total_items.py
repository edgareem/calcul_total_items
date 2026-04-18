#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Analyse des besoins de farm pour remplir un coffre de 27 slots pour chaque item.

Entrées :
- items.json
- recipes.json

Hypothèses :
- Les deux fichiers sont à la racine, au même niveau que ce script.
- On veut remplir 27 slots pour chaque item.
- La quantité cible d'un item = 27 * stackSize.
- On utilise une liste manuelle de ressources "base farmables".
- On choisit la recette qui minimise le coût en ressources de base.
- Les recettes réversibles sont gérées naturellement, avec protection anti-cycle.

Sorties :
- farming_summary.json : résultat complet
- farming_totals.txt    : résumé lisible
"""

from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any

from openpyxl import load_workbook


# =========================
# Configuration utilisateur
# =========================

CHEST_SLOTS = 27

# Liste des ressources qu'on considère comme "à farmer".
# Dès qu'on atteint un de ces items, on s'arrête.
BASE_FARMABLES_BY_NAME = {
    # Bois
    "oak_log", "spruce_log", "birch_log", "jungle_log", "acacia_log",
    "dark_oak_log", "mangrove_log", "cherry_log", "pale_oak_log",
    "crimson_stem", "warped_stem",

    # Pierre / terre / sable
    "cobblestone", "blackstone", "basalt", "sand", "red_sand",
    "gravel", "clay_ball", "netherrack", "end_stone", "obsidian",

    # Minerais / ressources brutes
    "raw_iron", "raw_copper", "raw_gold", "coal", "charcoal",
    "redstone", "lapis_lazuli", "diamond", "emerald", "quartz",
    "amethyst_shard", "flint",

    # Mob / loot / organique
    "bone", "string", "slime_ball", "gunpowder", "leather",
    "feather", "egg", "wheat", "sugar_cane", "melon_slice",
    "pumpkin", "cocoa_beans", "honeycomb", "bamboo", "stick",

    # Autres utiles
    "netherite_scrap", "ancient_debris", "blaze_rod", "ender_pearl",
}

# Items à exclure complètement du calcul, même s'ils ne viennent pas du fichier Excel
STATIC_EXCLUDED_ITEMS_BY_NAME = {
    "farmland",   # pas un item normal de stockage
}

ITEMS_FILE = Path("items.json")
RECIPES_FILE = Path("recipes.json")
EXCEL_FILE = Path("MC_Ultimate List.xlsx")
OUTPUT_JSON = Path("farming_summary.json")
OUTPUT_TXT = Path("farming_totals.txt")
OUTPUT_TREE_TXT = Path("farming_recipe_trees.txt")

VERBOSE_EXCEL_EVERY = 1000


# =========================
# Chargement des données
# =========================

def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def build_item_maps(items_data: List[Dict[str, Any]]) -> Tuple[Dict[int, dict], Dict[str, dict]]:
    by_id = {}
    by_name = {}
    for item in items_data:
        by_id[item["id"]] = item
        by_name[item["name"]] = item
    return by_id, by_name


def build_item_name_from_display_map(items_data: List[Dict[str, Any]]) -> Dict[str, str]:
    display_to_name = {}
    for item in items_data:
        display_name = item.get("displayName")
        item_name = item.get("name")
        if display_name and item_name and display_name not in display_to_name:
            display_to_name[display_name] = item_name
    return display_to_name


def normalize_item_lookup_key(value: str) -> str:
    return str(value).strip().lower().replace(" ", "_")


def build_item_lookup_map(items_data: List[Dict[str, Any]]) -> Dict[str, str]:
    lookup = {}
    for item in items_data:
        item_name = item.get("name")
        display_name = item.get("displayName")
        if not item_name:
            continue

        for candidate in (item_name, display_name, normalize_item_lookup_key(item_name)):
            if candidate:
                lookup.setdefault(str(candidate).strip(), item_name)
                lookup.setdefault(normalize_item_lookup_key(str(candidate)), item_name)

        if display_name:
            display_as_name = normalize_item_lookup_key(display_name)
            lookup.setdefault(display_as_name, item_name)

    return lookup


def load_excluded_items_from_excel(
    excel_path: Path,
    items_by_name: Dict[str, dict],
    item_lookup_map: Dict[str, str],
) -> Set[str]:
    if not excel_path.exists():
        raise FileNotFoundError(f"Fichier introuvable: {excel_path}")

    print(f"[Excel] Ouverture du fichier : {excel_path}", flush=True)
    workbook = load_workbook(excel_path, read_only=True, data_only=True)
    try:
        sheet_name = "items" if "items" in workbook.sheetnames else "Items"
        worksheet = workbook[sheet_name]
        print(f"[Excel] Feuille utilisee : {sheet_name}", flush=True)

        header_row = next(
            worksheet.iter_rows(min_row=2, max_row=2, values_only=True),
            None,
        )
        if header_row is None:
            raise ValueError("Impossible de lire la ligne d'entetes du fichier Excel.")

        headers = {
            str(value).strip().lower(): index
            for index, value in enumerate(header_row)
            if value is not None
        }

        item_name_col = headers.get("item name")
        creative_only_col = headers.get("creative only")

        if item_name_col is None or creative_only_col is None:
            raise ValueError("Colonnes Excel introuvables: 'Item Name' ou 'Creative Only'.")

        excluded_items = set(STATIC_EXCLUDED_ITEMS_BY_NAME)
        print(f"[Excel] Debut de lecture des lignes de donnees...", flush=True)

        for row_number, row_values in enumerate(
            worksheet.iter_rows(min_row=5, values_only=True),
            start=5,
        ):
            excel_item_name = row_values[item_name_col] if item_name_col < len(row_values) else None
            creative_only = row_values[creative_only_col] if creative_only_col < len(row_values) else None

            # Affichage regulier pour confirmer que la lecture avance.
            if row_number == 5 or row_number % VERBOSE_EXCEL_EVERY == 0:
                print(
                    f"[Excel] Ligne {row_number}: item={excel_item_name!r}, creative_only={creative_only!r}",
                    flush=True,
                )

            if creative_only is not True or not excel_item_name:
                continue

            raw_excel_item_name = str(excel_item_name).strip()
            normalized_excel_item_name = normalize_item_lookup_key(raw_excel_item_name)
            resolved_name = (
                item_lookup_map.get(raw_excel_item_name)
                or item_lookup_map.get(normalized_excel_item_name)
            )
            if resolved_name and resolved_name in items_by_name:
                excluded_items.add(resolved_name)
                print(
                    f"[Excel] Exclusion ajoutee ligne {row_number}: {excel_item_name} -> {resolved_name}",
                    flush=True,
                )
            else:
                print(
                    f"[Excel] Item non resolu ligne {row_number}: {excel_item_name!r}",
                    flush=True,
                )

        print(f"[Excel] Lecture terminee. Total exclus: {len(excluded_items)}", flush=True)
        return excluded_items
    finally:
        workbook.close()


def print_progress(current: int, total: int, width: int = 40) -> None:
    if total <= 0:
        return

    progress_ratio = current / total
    filled = int(width * progress_ratio)
    bar = "#" * filled + "-" * (width - filled)
    print(f"\rProgression: [{bar}] {current}/{total} ({progress_ratio:.1%})", end="", flush=True)

    if current >= total:
        print()


# =========================
# Parsing des recettes
# =========================

def extract_ingredients_from_recipe(recipe: Dict[str, Any]) -> Counter:
    """
    Retourne un Counter {item_id: quantité} pour une recette.

    Gère :
    - inShape : grille avec répétitions des ids
    - ingredients : liste d'ingrédients
    """
    ingredients = Counter()

    if "inShape" in recipe and recipe["inShape"] is not None:
        for row in recipe["inShape"]:
            for cell in row:
                if cell is not None:
                    ingredients[cell] += 1

    elif "ingredients" in recipe and recipe["ingredients"] is not None:
        for ing in recipe["ingredients"]:
            if ing is not None:
                ingredients[ing] += 1

    return ingredients


def normalize_recipes(raw_recipes: Dict[str, List[Dict[str, Any]]]) -> Dict[int, List[Dict[str, Any]]]:
    """
    Transforme recipes.json en structure plus simple :
    {
      result_item_id: [
        {
          "result_id": int,
          "result_count": int,
          "ingredients": Counter({ingredient_id: qty, ...}),
          "raw": recipe_originale
        },
        ...
      ]
    }
    """
    normalized = defaultdict(list)

    for result_id_str, recipe_list in raw_recipes.items():
        try:
            result_id_from_key = int(result_id_str)
        except ValueError:
            continue

        if not isinstance(recipe_list, list):
            continue

        for recipe in recipe_list:
            result = recipe.get("result")
            if not result or "id" not in result:
                continue

            result_id = result["id"]
            result_count = int(result.get("count", 1))

            # Sécurité si la clé et le result.id divergent
            if result_id != result_id_from_key:
                pass

            ingredients = extract_ingredients_from_recipe(recipe)

            normalized[result_id].append({
                "result_id": result_id,
                "result_count": result_count,
                "ingredients": ingredients,
                "raw": recipe
            })

    return dict(normalized)


# =========================
# Outils de calcul
# =========================

class ResolutionError(Exception):
    pass


def counter_to_named_dict(counter: Counter, items_by_id: Dict[int, dict]) -> Dict[str, int]:
    result = {}
    for item_id, qty in sorted(counter.items(), key=lambda kv: items_by_id.get(kv[0], {}).get("name", str(kv[0]))):
        item = items_by_id.get(item_id)
        name = item["name"] if item else f"unknown_{item_id}"
        result[name] = int(qty)
    return result


def multiply_counter(counter: Counter, factor: int) -> Counter:
    return Counter({k: v * factor for k, v in counter.items()})


def merge_counters(a: Counter, b: Counter) -> Counter:
    result = Counter(a)
    result.update(b)
    return result


def total_base_cost(counter: Counter) -> int:
    """
    Mesure simple du "coût" :
    somme des quantités de ressources de base.
    """
    return sum(counter.values())


# =========================
# Résolution récursive
# =========================

class CraftAnalyzer:
    def __init__(
        self,
        items_by_id: Dict[int, dict],
        items_by_name: Dict[str, dict],
        recipes_by_result: Dict[int, List[Dict[str, Any]]],
        base_farmables_by_name: Set[str],
        excluded_items_by_name: Set[str],
    ):
        self.items_by_id = items_by_id
        self.items_by_name = items_by_name
        self.recipes_by_result = recipes_by_result

        self.base_farmable_ids = {
            self.items_by_name[name]["id"]
            for name in base_farmables_by_name
            if name in self.items_by_name
        }
        self.excluded_item_ids = {
            self.items_by_name[name]["id"]
            for name in excluded_items_by_name
            if name in self.items_by_name
        }

        # Mémoisation : (item_id, qty) -> résultat
        self.memo: Dict[Tuple[int, int], Dict[str, Any]] = {}

    def item_name(self, item_id: int) -> str:
        item = self.items_by_id.get(item_id)
        return item["name"] if item else f"unknown_{item_id}"

    def is_excluded(self, item_id: int) -> bool:
        return item_id in self.excluded_item_ids

    def is_base_farmable(self, item_id: int) -> bool:
        return item_id in self.base_farmable_ids

    def has_recipe(self, item_id: int) -> bool:
        return item_id in self.recipes_by_result and len(self.recipes_by_result[item_id]) > 0

    def resolve_item(
        self,
        item_id: int,
        required_qty: int,
        visiting: Optional[Set[int]] = None
    ) -> Dict[str, Any]:
        """
        Retourne un dict :
        {
          "base_resources": Counter,
          "unresolved": Counter,
          "excluded": Counter,
          "recipe_used": dict | None
        }
        """
        if visiting is None:
            visiting = set()

        memo_key = (item_id, required_qty)
        if memo_key in self.memo:
            return deepcopy(self.memo[memo_key])

        if required_qty <= 0:
            result = {
                "base_resources": Counter(),
                "unresolved": Counter(),
                "excluded": Counter(),
                "recipe_used": None
            }
            self.memo[memo_key] = deepcopy(result)
            return result

        # Exclu
        if self.is_excluded(item_id):
            result = {
                "base_resources": Counter(),
                "unresolved": Counter(),
                "excluded": Counter({item_id: required_qty}),
                "recipe_used": None
            }
            self.memo[memo_key] = deepcopy(result)
            return result

        # Ressource de base
        if self.is_base_farmable(item_id):
            result = {
                "base_resources": Counter({item_id: required_qty}),
                "unresolved": Counter(),
                "excluded": Counter(),
                "recipe_used": None
            }
            self.memo[memo_key] = deepcopy(result)
            return result

        # Anti-cycle
        if item_id in visiting:
            result = {
                "base_resources": Counter(),
                "unresolved": Counter({item_id: required_qty}),
                "excluded": Counter(),
                "recipe_used": None
            }
            self.memo[memo_key] = deepcopy(result)
            return result

        # Pas de recette => non résolu => on considère qu'on doit le farmer tel quel
        # ou au moins le signaler.
        if not self.has_recipe(item_id):
            result = {
                "base_resources": Counter(),
                "unresolved": Counter({item_id: required_qty}),
                "excluded": Counter(),
                "recipe_used": None
            }
            self.memo[memo_key] = deepcopy(result)
            return result

        visiting = set(visiting)
        visiting.add(item_id)

        candidate_results = []

        for recipe in self.recipes_by_result[item_id]:
            result_count = recipe["result_count"]
            ingredients = recipe["ingredients"]

            if result_count <= 0:
                continue

            crafts_needed = math.ceil(required_qty / result_count)

            aggregate_base = Counter()
            aggregate_unresolved = Counter()
            aggregate_excluded = Counter()

            valid = True

            for ingredient_id, ingredient_qty in ingredients.items():
                needed_ingredient_qty = ingredient_qty * crafts_needed
                sub = self.resolve_item(ingredient_id, needed_ingredient_qty, visiting=visiting)

                aggregate_base.update(sub["base_resources"])
                aggregate_unresolved.update(sub["unresolved"])
                aggregate_excluded.update(sub["excluded"])

            candidate_results.append({
                "base_resources": aggregate_base,
                "unresolved": aggregate_unresolved,
                "excluded": aggregate_excluded,
                "recipe_used": {
                    "result_id": recipe["result_id"],
                    "result_count": recipe["result_count"],
                    "ingredients": dict(recipe["ingredients"]),
                    "crafts_needed": crafts_needed
                },
                "score": (
                    sum(aggregate_unresolved.values()),  # d'abord minimiser les non résolus
                    total_base_cost(aggregate_base),      # puis minimiser les ressources de base
                    sum(aggregate_excluded.values())      # puis les exclus
                )
            })

        if not candidate_results:
            result = {
                "base_resources": Counter(),
                "unresolved": Counter({item_id: required_qty}),
                "excluded": Counter(),
                "recipe_used": None
            }
            self.memo[memo_key] = deepcopy(result)
            return result

        best = min(candidate_results, key=lambda x: x["score"])

        result = {
            "base_resources": best["base_resources"],
            "unresolved": best["unresolved"],
            "excluded": best["excluded"],
            "recipe_used": best["recipe_used"]
        }
        self.memo[memo_key] = deepcopy(result)
        return result

    def target_quantity_for_item(self, item_id: int) -> int:
        item = self.items_by_id[item_id]
        stack_size = int(item.get("stackSize", 64))
        if stack_size <= 0:
            stack_size = 1
        return CHEST_SLOTS * stack_size


# =========================
# Analyse globale
# =========================

def analyze_all_items():
    if not ITEMS_FILE.exists():
        raise FileNotFoundError(f"Fichier introuvable: {ITEMS_FILE}")
    if not RECIPES_FILE.exists():
        raise FileNotFoundError(f"Fichier introuvable: {RECIPES_FILE}")
    if not EXCEL_FILE.exists():
        raise FileNotFoundError(f"Fichier introuvable: {EXCEL_FILE}")

    print(f"[Init] Chargement de {ITEMS_FILE}...", flush=True)
    items_data = load_json(ITEMS_FILE)
    print(f"[Init] {len(items_data)} items charges.", flush=True)

    print(f"[Init] Chargement de {RECIPES_FILE}...", flush=True)
    recipes_data = load_json(RECIPES_FILE)
    print(f"[Init] {len(recipes_data)} entrees de recettes chargees.", flush=True)

    items_by_id, items_by_name = build_item_maps(items_data)
    item_lookup_map = build_item_lookup_map(items_data)
    recipes_by_result = normalize_recipes(recipes_data)
    excluded_items_by_name = load_excluded_items_from_excel(
        excel_path=EXCEL_FILE,
        items_by_name=items_by_name,
        item_lookup_map=item_lookup_map,
    )

    analyzer = CraftAnalyzer(
        items_by_id=items_by_id,
        items_by_name=items_by_name,
        recipes_by_result=recipes_by_result,
        base_farmables_by_name=BASE_FARMABLES_BY_NAME,
        excluded_items_by_name=excluded_items_by_name,
    )

    grand_total_base = Counter()
    grand_total_unresolved = Counter()
    grand_total_excluded = Counter()

    per_item_details = {}

    # Tri pour avoir une sortie stable
    all_item_ids = sorted(items_by_id.keys(), key=lambda i: items_by_id[i]["name"])
    item_ids_to_process = [item_id for item_id in all_item_ids if item_id not in analyzer.excluded_item_ids]
    total_items_to_process = len(item_ids_to_process)
    print(f"[Init] {total_items_to_process} items a analyser.", flush=True)

    # Les items exclus par l'Excel sont retires du calcul principal, donc on les
    # ajoute explicitement au recapitulatif final pour qu'ils apparaissent bien.
    excluded_items_summary = Counter(
        {
            item_id: analyzer.target_quantity_for_item(item_id)
            for item_id in sorted(analyzer.excluded_item_ids, key=lambda i: items_by_id[i]["name"])
        }
    )

    for index, item_id in enumerate(item_ids_to_process, start=1):
        item = items_by_id[item_id]
        item_name = item["name"]

        target_qty = analyzer.target_quantity_for_item(item_id)
        print(
            f"[Analyse] Item {index}/{total_items_to_process} - ligne logique {index}: {item_name} (quantite cible: {target_qty})",
            flush=True,
        )
        resolution = analyzer.resolve_item(item_id, target_qty)

        grand_total_base.update(resolution["base_resources"])
        grand_total_unresolved.update(resolution["unresolved"])
        grand_total_excluded.update(resolution["excluded"])

        per_item_details[item_name] = {
            "item_id": item_id,
            "display_name": item.get("displayName", item_name),
            "stack_size": item.get("stackSize", 64),
            "target_quantity": target_qty,
            "base_resources": counter_to_named_dict(resolution["base_resources"], items_by_id),
            "unresolved": counter_to_named_dict(resolution["unresolved"], items_by_id),
            "excluded": counter_to_named_dict(resolution["excluded"], items_by_id),
            "recipe_used": format_recipe_used(resolution["recipe_used"], items_by_id),
        }

        print_progress(index, total_items_to_process)

    summary = {
        "config": {
            "chest_slots": CHEST_SLOTS,
            "base_farmables": sorted(BASE_FARMABLES_BY_NAME),
            "excluded_items": sorted(excluded_items_by_name),
        },
        "global_totals": {
            "base_resources": counter_to_named_dict(grand_total_base, items_by_id),
            "unresolved": counter_to_named_dict(grand_total_unresolved, items_by_id),
            "excluded": counter_to_named_dict(
                merge_counters(grand_total_excluded, excluded_items_summary),
                items_by_id,
            ),
        },
        "per_item_details": per_item_details,
    }

    with OUTPUT_JSON.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    write_recipe_tree_summary(
        analyzer=analyzer,
        item_ids_to_process=item_ids_to_process,
    )

    write_human_readable_summary(
        items_by_id=items_by_id,
        grand_total_base=grand_total_base,
        grand_total_unresolved=grand_total_unresolved,
        grand_total_excluded=merge_counters(grand_total_excluded, excluded_items_summary),
        per_item_details=per_item_details,
    )

    print(f"Analyse terminée.")
    print(f"- Résumé JSON : {OUTPUT_JSON}")
    print(f"- Résumé texte : {OUTPUT_TXT}")


def format_recipe_used(recipe_used: Optional[Dict[str, Any]], items_by_id: Dict[int, dict]) -> Optional[Dict[str, Any]]:
    if recipe_used is None:
        return None

    ingredients_named = {}
    for item_id, qty in recipe_used["ingredients"].items():
        name = items_by_id.get(int(item_id), {}).get("name", f"unknown_{item_id}")
        ingredients_named[name] = qty

    return {
        "result_id": recipe_used["result_id"],
        "result_name": items_by_id.get(recipe_used["result_id"], {}).get("name", f"unknown_{recipe_used['result_id']}"),
        "result_count": recipe_used["result_count"],
        "crafts_needed": recipe_used["crafts_needed"],
        "ingredients": ingredients_named,
    }


def build_recipe_tree_lines(
    analyzer: CraftAnalyzer,
    item_id: int,
    required_qty: int = 1,
    depth: int = 0,
    visiting: Optional[Set[int]] = None,
) -> List[str]:
    if visiting is None:
        visiting = set()

    item_name = analyzer.item_name(item_id)
    if depth == 0:
        lines = [item_name]
    else:
        lines = [f"{'    ' * depth}└── {item_name} x{required_qty}"]

    if item_id in visiting:
        lines[-1] += " [cycle]"
        return lines

    if analyzer.is_excluded(item_id):
        lines[-1] += " [exclu]"
        return lines

    if analyzer.is_base_farmable(item_id):
        return lines

    if not analyzer.has_recipe(item_id):
        lines[-1] += " [non resolu]"
        return lines

    resolution = analyzer.resolve_item(item_id, required_qty)
    recipe_used = resolution.get("recipe_used")
    if not recipe_used:
        return lines

    next_visiting = set(visiting)
    next_visiting.add(item_id)

    for ingredient_id, ingredient_qty in sorted(
        recipe_used["ingredients"].items(),
        key=lambda kv: analyzer.item_name(int(kv[0])),
    ):
        child_required_qty = ingredient_qty * recipe_used["crafts_needed"]
        lines.extend(
            build_recipe_tree_lines(
                analyzer=analyzer,
                item_id=int(ingredient_id),
                required_qty=child_required_qty,
                depth=depth + 1,
                visiting=next_visiting,
            )
        )

    return lines


def build_recipe_tree_lines_v2(
    analyzer: CraftAnalyzer,
    item_id: int,
    required_qty: int = 1,
    depth: int = 0,
    visiting: Optional[Set[int]] = None,
) -> List[str]:
    if visiting is None:
        visiting = set()

    item_name = analyzer.item_name(item_id)
    produced_qty = required_qty
    recipe_used = None

    if analyzer.has_recipe(item_id):
        resolution = analyzer.resolve_item(item_id, required_qty)
        recipe_used = resolution.get("recipe_used")
        if recipe_used:
            produced_qty = recipe_used["result_count"] * recipe_used["crafts_needed"]

    if depth == 0:
        lines = [f"{item_name} x{produced_qty} (pour {required_qty} craft)"]
    else:
        lines = [f"{'    ' * depth}\\-- {item_name} x{required_qty}"]

    if item_id in visiting:
        lines[-1] += " [cycle]"
        return lines

    if analyzer.is_excluded(item_id):
        lines[-1] += " [exclu]"
        return lines

    if analyzer.is_base_farmable(item_id):
        return lines

    if not analyzer.has_recipe(item_id):
        lines[-1] += " [non resolu]"
        return lines

    if not recipe_used:
        return lines

    next_visiting = set(visiting)
    next_visiting.add(item_id)

    for ingredient_id, ingredient_qty in sorted(
        recipe_used["ingredients"].items(),
        key=lambda kv: analyzer.item_name(int(kv[0])),
    ):
        child_required_qty = ingredient_qty * recipe_used["crafts_needed"]
        lines.extend(
            build_recipe_tree_lines_v2(
                analyzer=analyzer,
                item_id=int(ingredient_id),
                required_qty=child_required_qty,
                depth=depth + 1,
                visiting=next_visiting,
            )
        )

    return lines


def write_recipe_tree_summary(
    analyzer: CraftAnalyzer,
    item_ids_to_process: List[int],
):
    lines = [
        "=== ARBORESCENCE DES RECETTES ===",
        "Chaque arbre correspond a 1 craft de l'item.",
    ]

    for item_id in item_ids_to_process:
        lines.append("")
        lines.extend(build_recipe_tree_lines_v2(analyzer=analyzer, item_id=item_id, required_qty=1))

    with OUTPUT_TREE_TXT.open("w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def write_human_readable_summary(
    items_by_id: Dict[int, dict],
    grand_total_base: Counter,
    grand_total_unresolved: Counter,
    grand_total_excluded: Counter,
    per_item_details: Dict[str, Any],
):
    lines = []

    lines.append("=== TOTAL GLOBAL DES RESSOURCES À FARMER ===")
    if grand_total_base:
        for item_id, qty in sorted(grand_total_base.items(), key=lambda kv: items_by_id[kv[0]]["name"]):
            lines.append(f"- {items_by_id[item_id]['name']}: {qty}")
    else:
        lines.append("(aucune)")

    lines.append("")
    lines.append("=== ITEMS NON RÉSOLUS ===")
    if grand_total_unresolved:
        for item_id, qty in sorted(grand_total_unresolved.items(), key=lambda kv: items_by_id.get(kv[0], {}).get("name", str(kv[0]))):
            name = items_by_id.get(item_id, {}).get("name", f"unknown_{item_id}")
            lines.append(f"- {name}: {qty}")
    else:
        lines.append("(aucun)")

    lines.append("")
    lines.append("=== ITEMS EXCLUS ===")
    if grand_total_excluded:
        for item_id, qty in sorted(grand_total_excluded.items(), key=lambda kv: items_by_id.get(kv[0], {}).get("name", str(kv[0]))):
            name = items_by_id.get(item_id, {}).get("name", f"unknown_{item_id}")
            lines.append(f"- {name}: {qty}")
    else:
        lines.append("(aucun)")

    lines.append("")
    lines.append("=== DÉTAIL PAR ITEM ===")

    for item_name in sorted(per_item_details.keys()):
        detail = per_item_details[item_name]
        lines.append("")
        lines.append(f"[{item_name}]")
        lines.append(f"  - target_quantity: {detail['target_quantity']}")
        lines.append(f"  - stack_size: {detail['stack_size']}")

        if detail["recipe_used"]:
            lines.append("  - recipe_used:")
            lines.append(f"      result_count: {detail['recipe_used']['result_count']}")
            lines.append(f"      crafts_needed: {detail['recipe_used']['crafts_needed']}")
            lines.append("      ingredients:")
            for ing_name, ing_qty in sorted(detail["recipe_used"]["ingredients"].items()):
                lines.append(f"        - {ing_name}: {ing_qty}")
        else:
            lines.append("  - recipe_used: none")

        lines.append("  - base_resources:")
        if detail["base_resources"]:
            for res_name, res_qty in sorted(detail["base_resources"].items()):
                lines.append(f"      - {res_name}: {res_qty}")
        else:
            lines.append("      (none)")

        lines.append("  - unresolved:")
        if detail["unresolved"]:
            for res_name, res_qty in sorted(detail["unresolved"].items()):
                lines.append(f"      - {res_name}: {res_qty}")
        else:
            lines.append("      (none)")

        lines.append("  - excluded:")
        if detail["excluded"]:
            for res_name, res_qty in sorted(detail["excluded"].items()):
                lines.append(f"      - {res_name}: {res_qty}")
        else:
            lines.append("      (none)")

    with OUTPUT_TXT.open("w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    analyze_all_items()
