# Visiteurs (Home Assistant)

Gère les visiteurs simplement, depuis le téléphone, la tablette ou l'agenda :

- **Deux types de visite** : *reste sur place* (famille, amis qui dorment ou gardent la maison : comptent comme une présence) et *passage* (artisan, livreur, voisin qui nourrit les animaux).
- **Visite prévue ou « là maintenant »**. Début et fin automatiques à l'heure près, avec une marge réglable avant et après.
- **Code visiteur temporaire** (module *Codes d'accès* ≥ 1.1) : sur les tablettes murales (bouton 🔑 « Visiteur »), seulement pendant la visite, seulement pour les accès cochés. Un code visiteur ne désarme jamais l'alarme, sauf si on coche « peut désarmer » pour cette visite. Chaque usage est signalé. 5 codes faux : codes visiteur bloqués (5 min, puis plus).
- **Message d'accueil** prêt à envoyer (SMS, copier, partager) : dates, code et ce qu'il ouvre, Wi-Fi invité, consignes.
- **Page d'accueil** pour la tablette : « Bienvenue Marc ! », QR code du Wi-Fi invité, mot de passe, consignes.
- **Véhicule** : plaque du visiteur reconnue (lecture tolérante) par l'action `visiteurs.reconnaitre_plaque`.
- **Lumière d'accueil** allumée au début d'une visite s'il fait nuit, éteinte à 23 h.

## Entités

| Entité | Rôle |
|---|---|
| `binary_sensor.visiteurs_invites_sur_place` | Au moins un invité « reste sur place » en ce moment (à combiner avec la présence de la famille). |
| `binary_sensor.visiteurs_passage_en_cours` | Un passage en cours (artisan…). Attribut `noms`. |
| `binary_sensor.visiteurs_nuit_visiteurs` | Plage de nuit des options (alertes caméra maintenues la nuit). Masquée. |
| `sensor.visiteurs_visites_en_cours` | Nombre de visites ; attributs `visites`, `noms`, `plaques` ({plaque: nom}). |
| `sensor.visiteurs_prochaine_visite` | Heure de la prochaine arrivée ; attribut `nom`. |
| `calendar.visiteurs` | Agenda : voir et ajouter des visites (« passage » dans la description → passage). |

Événements : `visiteurs_debut`, `visiteurs_fin` (`id`, `nom`, `type`, `debut`, `fin`, `site`), `visiteurs_modifie`.

## Actions

`visiteurs.ajouter` (réponse : `id`, `code`, `message`), `visiteurs.modifier`, `visiteurs.terminer`, `visiteurs.supprimer`, `visiteurs.arrivee`, `visiteurs.reconnaitre_plaque` (réponse : `trouve`, `nom`, `type`, `id`).

Droits : comptes reliés à une personne (ou ceux choisis dans les options), jamais une tablette murale. Les automatisations peuvent tout faire.

## Carte

```yaml
type: custom:visiteurs-card
mode: auto        # auto : tablette murale → accueil, sinon gestion ; ou gestion / accueil
title: Visiteurs
```

## Réglages (options de l'intégration)

Accès qu'un code peut ouvrir, Wi-Fi invité (nom, mot de passe, sécurité), consignes, lumière d'accueil, durées par défaut (passage 2 h, séjour 24 h), marges (30 min), plage de nuit (22 h – 6 h), qui prévenir et de quoi, qui peut gérer.

## Limites

- Le mot de passe du Wi-Fi invité est visible de tous les comptes (il est fait pour être donné) : ne pas y mettre celui du Wi-Fi principal.
- Le code visiteur est conservé lisible pour la famille (pour pouvoir le renvoyer) dans le stockage privé de Home Assistant, et haché pour la vérification.
- Codes visiteur : seulement sur les tablettes murales (comptes « TabDomo… »). Pas encore sur les lecteurs physiques (UniFi Access).

## Tests

`tests/test_visites.py` (fonctions pures, 10), `tests/bench_visiteurs.py` (45 contrôles + 2 après redémarrage sur un vrai Home Assistant avec *Codes d'accès* 1.1), `tests/card_test.py` (23 contrôles dans Chromium : ordinateur, téléphone 380 px, tablette).
