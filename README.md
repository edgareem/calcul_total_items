# 🪓 Minecraft Farming Challenge Calculator

Ce projet permet de calculer combien d'items tu dois farmer ou miner pour reussir un defi Minecraft.

## ⚙️ Inputs

Le script utilise :

- `📦 items.json` : liste complete des items du jeu
- `🛠️ recipes.json` : toutes les recettes de craft
- `📊 MC_Ultimate List.xlsx` : permet de filtrer les items `creative only` pour ne garder que les items legit survival

## 🎯 Objectif

👉 Pour chaque item du jeu, le script cherche a :

- remplir un coffre complet de `27` stacks
- calculer tous les crafts necessaires
- remonter jusqu'aux ressources a farmer

## 📤Outputs

Le script genere :

- `📄 farming_totals.txt`
  Total global des ressources a farmer, par exemple combien de buches, de cobblestone ou de minerais.
- `📁 farming_summary.json`
  Detail complet des calculs par item.
- `🌳 farming_recipe_trees.txt`
  Arbre des recettes pour comprendre comment chaque item est crafté.

## 🧠 Resume

👉 Le script simule un run survival hardcore ou tu dois :

- crafter tous les items du jeu
- remplir un coffre de chaque item
- savoir exactement combien de ressources grinder 😈

## ⚠️ Notes

- Les items `creative only` sont exclus.
- Le calcul prend en compte les recettes, y compris les quantites produites par craft.
- Les ressources finales correspondent a ce que tu dois reellement farmer dans le monde.

## 🔥 Use Cases

👉 Parfait pour :

- les defis Minecraft 🧱
- l'optimisation de farming ⛏️
- le theorycraft hardcore

