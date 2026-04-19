# Minecraft Farming Challenge Calculator

Ce projet sert a calculer combien de ressources il faut farmer, miner ou recuperer pour completer un objectif Minecraft de grande ampleur.

L'idee generale est la suivante :
- partir d'une liste d'items a conserver dans le musee
- calculer la quantite cible de chaque item
- remonter les recettes de craft jusqu'aux ressources de base
- produire des fichiers lisibles pour analyser les besoins

Le projet est pense comme un outil de calcul, mais aussi comme un support pedagogique pour expliquer du Python a des debutants.

## Structure du projet

### Dossier d'entree

Les fichiers d'entree bruts se trouvent dans [entree](</c:/Angel/Projets/Minecraft_python/entree>) :

- [entree/items.json](</c:/Angel/Projets/Minecraft_python/entree/items.json>)
  Liste complete des items Minecraft. Chaque entree contient par exemple le `name`, le `displayName`, l'id et la taille de stack.
- [entree/recipes.json](</c:/Angel/Projets/Minecraft_python/entree/recipes.json>)
  Liste des recettes de craft.
- [entree/Musee_Infinis_clean.xlsx](</c:/Angel/Projets/Minecraft_python/entree/Musee_Infinis_clean.xlsx>)
  Fichier Excel du musee. La colonne `english_name` sert a definir quels items on garde reellement dans le calcul.

### Scripts principaux

- [Calcul_total_items.py](</c:/Angel/Projets/Minecraft_python/Calcul_total_items.py>)
  Script principal de calcul.
- [clean_museum_totals.py](</c:/Angel/Projets/Minecraft_python/clean_museum_totals.py>)
  Script de nettoyage et de mise en forme du fichier Excel final.
- [list_duplicate_recipe_results.py](</c:/Angel/Projets/Minecraft_python/list_duplicate_recipe_results.py>)
  Script d'audit des recettes qui ont plusieurs crafts possibles pour un meme resultat.

### Fichier de configuration

- [selected_recipe_choices.json](</c:/Angel/Projets/Minecraft_python/selected_recipe_choices.json>)
  Permet de forcer le craft a utiliser quand un item possede plusieurs recettes.

Exemple :

```json
{
  "barrel": 12,
  "cake": 3,
  "torch": 2
}
```

Cela signifie que, pour ces items, le calcul principal ne doit garder que le numero de craft indique.

## Script 1 : Calcul_total_items.py

### Role

Ce script fait le gros du travail.

Il :
- charge les items et les recettes
- charge la liste des items du musee a partir de l'Excel
- filtre les items a traiter
- choisit les recettes a utiliser
- calcule les besoins de craft et de farm
- genere plusieurs fichiers de sortie

### Logique metier importante

Le script applique plusieurs regles metier :

- la quantite cible d'un item correspond a un coffre complet, donc `27 * stackSize`
- seuls les items presents dans l'Excel du musee sont gardes
- certains items sont consideres comme des ressources de base a farmer directement
- certaines formes reversibles sont normalisees pour eviter des conversions inutiles
  Exemple : `iron_nugget` et `iron_block` sont ramenes vers `iron_ingot`
- certaines recettes multiples peuvent etre forcees via `selected_recipe_choices.json`
- des ajustements manuels peuvent etre ajoutes a certains totaux

### Entrees utilisees

- [entree/items.json](</c:/Angel/Projets/Minecraft_python/entree/items.json>)
- [entree/recipes.json](</c:/Angel/Projets/Minecraft_python/entree/recipes.json>)
- [entree/Musee_Infinis_clean.xlsx](</c:/Angel/Projets/Minecraft_python/entree/Musee_Infinis_clean.xlsx>)
- [selected_recipe_choices.json](</c:/Angel/Projets/Minecraft_python/selected_recipe_choices.json>)

### Sorties generees

Toutes les sorties de ce script sont placees dans le dossier [sortie calcul totaux](</c:/Angel/Projets/Minecraft_python/sortie%20calcul%20totaux>) :

- [sortie calcul totaux/farming_summary.json](</c:/Angel/Projets/Minecraft_python/sortie%20calcul%20totaux/farming_summary.json>)
  Resume complet du calcul en JSON.
- [sortie calcul totaux/farming_totals.txt](</c:/Angel/Projets/Minecraft_python/sortie%20calcul%20totaux/farming_totals.txt>)
  Resume texte lisible des ressources a farmer.
- [sortie calcul totaux/farming_recipe_trees.txt](</c:/Angel/Projets/Minecraft_python/sortie%20calcul%20totaux/farming_recipe_trees.txt>)
  Arborescence de craft par item.
- [sortie calcul totaux/Musee_Infinis_clean_with_totals.xlsx](</c:/Angel/Projets/Minecraft_python/sortie%20calcul%20totaux/Musee_Infinis_clean_with_totals.xlsx>)
  Copie enrichie du fichier musee, avec les colonnes de calcul.

### Colonnes ajoutees dans l'Excel enrichi

Le fichier `Musee_Infinis_clean_with_totals.xlsx` ajoute :

- `Total Pour Items Craftables`
  Total calcule pour les ressources craftables.
- `Total cible item`
  Quantite cible de l'item lui-meme.
- `OnRecipes_Res`
  `true` si l'item apparait comme resultat dans `recipes.json`.
- `OnRecipes_Ingredient`
  `true` si l'item apparait comme ingredient dans `recipes.json`.

### Commande

```bash
python Calcul_total_items.py
```

## Script 2 : clean_museum_totals.py

### Role

Ce script prend le fichier Excel enrichi genere par `Calcul_total_items.py` et produit une version finale plus lisible.

Il :
- lit l'Excel enrichi
- reconstruit un nouveau tableau propre
- remet `Total a Farm` a `0` si l'item n'apparait dans aucune recette
- calcule l'equivalent en coffres

### Entree utilisee

- [sortie calcul totaux/Musee_Infinis_clean_with_totals.xlsx](</c:/Angel/Projets/Minecraft_python/sortie%20calcul%20totaux/Musee_Infinis_clean_with_totals.xlsx>)

### Sortie generee

- [sortie final clean/Musee_Infinis_clean_with_totals_clean.xlsx](</c:/Angel/Projets/Minecraft_python/sortie%20final%20clean/Musee_Infinis_clean_with_totals_clean.xlsx>)

### Colonnes finales

Le fichier final contient exactement :

- `Items`
- `Stack max`
- `Quantité requise`
- `english_name`
- `Total Pour Item Craftables`
- `Total à Farm`
- `Equialent Coffre`

### Regle de calcul de `Equialent Coffre`

La formule est :

```text
Equialent Coffre = ceil(Total à Farm / Quantité requise)
```

Exemples :
- `167.0 -> 167`
- `167.00001 -> 168`
- `167.796875 -> 168`

### Commande

```bash
python clean_museum_totals.py
```

## Script 3 : list_duplicate_recipe_results.py

### Role

Ce script sert a auditer les recettes Minecraft qui ont plusieurs crafts possibles pour un meme item resultat.

Il est utile pour :
- repérer les doublons de recettes
- voir le detail des ingredients de chaque variante
- choisir manuellement quel craft garder dans `selected_recipe_choices.json`

### Entrees utilisees

- [entree/items.json](</c:/Angel/Projets/Minecraft_python/entree/items.json>)
- [entree/recipes.json](</c:/Angel/Projets/Minecraft_python/entree/recipes.json>)

### Sortie generee

- [sortie doublons recettes/duplicate_recipe_results.txt](</c:/Angel/Projets/Minecraft_python/sortie%20doublons%20recettes/duplicate_recipe_results.txt>)

### Contenu du rapport

Pour chaque item avec plusieurs recettes, le fichier liste :
- le nom de l'item
- son id
- le nombre de recettes disponibles
- chaque craft numerote
- les ingredients de chaque craft
- la quantite produite par recette

### Commande

```bash
python list_duplicate_recipe_results.py
```

## Ordre d'utilisation recommande

Pour un cycle complet, l'ordre conseille est :

1. lancer `list_duplicate_recipe_results.py`
2. lire le rapport des doublons
3. mettre a jour `selected_recipe_choices.json`
4. lancer `Calcul_total_items.py`
5. lancer `clean_museum_totals.py`

## Sorties creees automatiquement

Quand les scripts sont lances, ils creent automatiquement ces dossiers si besoin :

- `sortie doublons recettes`
- `sortie calcul totaux`
- `sortie final clean`

## Objectif du projet

Ce projet est adapte pour :

- les defis Minecraft de collection complete
- l'optimisation de farm
- la planification d'un musee ou d'un entrepot complet
- le theorycraft autour des recettes Minecraft

En pratique, il sert a savoir combien il faut farmer pour obtenir tous les items voulus, avec une logique de craft precise et configurable.
