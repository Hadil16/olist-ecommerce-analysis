# Guide : construire le dashboard Power BI (étape par étape)

> **Un exemple complet existe déjà :** `olist_dashboard.pbip` (généré par `build_pbip.py`).
> 1. Ouvre `olist_dashboard.pbip` dans Power BI Desktop, clique **Refresh now** (deux fois, jusqu'à ce que les bannières disparaissent).
> 2. Fais **Fichier > Enregistrer sous** et enregistre en `dashboard\olist_dashboard.pbix`.
> 3. Pour vraiment apprendre : **refais ensuite le dashboard toi-même** avec ce guide, sans copier le fichier. Compare avec l'exemple à la fin.
> Les tables s'appellent `orders` et `items`, la table des mesures `_Measures`.

Fichier final à créer : `dashboard\olist_dashboard.pbix`
Objectif : un dashboard de 2 pages qui montre les mêmes résultats que le projet (Python et SQL).

## Étape 1 : importer les données
1. Ouvre **Power BI Desktop** puis **Obtenir les données > Texte/CSV**.
2. Charge `data\processed\orders_clean.csv` puis `data\processed\items_clean.csv`.
3. Clique sur **Transformer les données** et vérifie les types :
   - `order_purchase_timestamp`, `order_delivered_customer_date`, `order_estimated_delivery_date` : **Date/Heure**
   - `revenue`, `freight`, `price`, `freight_value`, `delivery_days`, `review_score` : **Nombre décimal**
   - `is_late` : **Vrai/Faux**
4. **Fermer et appliquer**.

## Étape 2 : le modèle de données
1. Onglet **Modélisation > Nouvelle table** : colle la table `Calendar` de `measures.dax`.
2. Va dans la vue **Modèle** et crée ces relations (glisser-déposer) :
   - `items_clean[order_id]` vers `orders_clean[order_id]` (plusieurs à un, filtre dans un seul sens)
   - `Calendar[Date]` vers `orders_clean[Purchase Date]` (un à plusieurs)
3. Ajoute les colonnes `Purchase Date`, `Delivery Status`, `Delivery Bucket` à `orders_clean`.
4. **Pourquoi ce modèle ?** Un ordre a plusieurs lignes dans `items_clean` (relation un-à-plusieurs, la même chose que le `JOIN` en SQL). La table `Calendar` permet de comparer les périodes.

## Étape 3 : les mesures DAX
Crée une table vide `_Measures` (Saisir des données) puis ajoute chaque mesure de `measures.dax`.

**Contrôle obligatoire :** pose chaque mesure dans une carte et compare avec la valeur attendue écrite dans les commentaires (par exemple Revenue = 13,181,027 et Late Rate = 8,1 %). Si un chiffre est différent, ne construis pas les visuels : cherche l'erreur d'abord. C'est exactement ce que fait un analyste professionnel.

## Étape 4 : page 1, "Executive Overview"
| Visuel | Champs |
|---|---|
| 6 cartes | Revenue, Delivered Orders, Average Order Value, Average Review Score, Late Rate, Repeat Rate |
| Histogramme + courbe | Axe `Calendar[Month]`, colonnes = Revenue, ligne = Delivered Orders |
| Barres horizontales (top 10) | `items_clean[category]`, valeur = Item Revenue (filtre Top 10) |
| Barres horizontales (top 10) | `orders_clean[customer_state]`, valeur = Revenue |
| Segments (slicers) | `Calendar[Year]`, `orders_clean[customer_state]` |

## Étape 5 : page 2, "Delivery & Customer Experience"
| Visuel | Champs |
|---|---|
| Courbe | Axe `Calendar[Month]`, valeur = Late Rate |
| Histogramme | Axe `Delivery Bucket`, valeur = Average Review Score |
| Histogramme (2 barres) | Axe `Delivery Status` (sans "n/a"), valeur = Average Review Score |
| Cartes | Average Delivery Days, Repeat Customers |
| Zone de texte | 3 conclusions (reprends celles du README) |

## Étape 6 : le design (ça compte pour les recruteurs)
- Couleurs : bleu `#1F5FA8`, orange `#E8833A`, gris `#9AA5B1`, rouge `#C0392B` (rouge uniquement pour les retards).
- Un titre clair par visuel, qui dit ce qu'il montre.
- Mets les 6 cartes en haut et les détails en bas. Pas de 3D, pas de camembert.
- Aligne tout avec **Format > Aligner**.

## Étape 7 : livrer
1. Enregistre : `dashboard\olist_dashboard.pbix`
2. Fais une capture de chaque page (`reports\figures\powerbi_page1.png`, `powerbi_page2.png`) pour le README et LinkedIn.
3. Dis-moi quand c'est fini : je relis ton dashboard comme un recruteur.

## Les 3 questions d'entretien sur cette partie
1. Pourquoi la relation entre `items_clean` et `orders_clean` est-elle "plusieurs à un" ?
2. Pourquoi `Revenue` filtre-t-il `order_status = "delivered"` ?
3. Quelle est la différence entre une colonne calculée et une mesure ?
