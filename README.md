# Visiteurs (Home Assistant)

Gère les visiteurs simplement, depuis le téléphone, la tablette ou l'agenda :

- **Deux types de visite** : *reste sur place* (famille, amis qui dorment ou gardent la maison : comptent comme une présence) et *passage* (artisan, livreur, voisin qui nourrit les animaux).
- **Passages réguliers** (femme de ménage, maréchal-ferrant, voisin qui nourrit les animaux…) : jours de la semaine, horaires, chaque semaine ou une sur deux / trois / quatre, sur une période (un an par défaut, deux au plus). Chaque passage commence et finit tout seul ; le code ne marche que pendant les passages ; « Pas cette fois » saute un passage, « Parti·e » arrête celui en cours.
- **« Dort ici »** : un visiteur de passage reste dormir (une nuit ou plus) — il compte alors comme « reste sur place », avec le même code et les mêmes accès ; ses passages habituels reprennent ensuite. « Annuler la nuit » revient en arrière.
- **Visite prévue ou « là maintenant »**. Début et fin automatiques à l'heure près, avec une marge réglable avant et après.
- **Code visiteur temporaire** (module *Codes d'accès* ≥ 1.1) : sur les tablettes murales (bouton 🔑 « Visiteur »), seulement pendant la visite, seulement pour les accès cochés. Un code visiteur ne désarme jamais l'alarme, sauf si on coche « peut désarmer » pour cette visite. Chaque usage est signalé. 5 codes faux : codes visiteur bloqués (5 min, puis plus).
- **Lecteurs UniFi Access** : si l'intégration UniFi Access est installée, ses portes (boutons « Déverrouiller ») peuvent être cochées comme accès. Pendant chaque visite (ou chaque passage), le code visiteur est créé sur le lecteur (visiteur UniFi Access avec ce PIN, ces portes et une heure de fin), puis supprimé à la fin. Jeton API UniFi Access avec les droits `view:visitor` et `edit:visitor`. Bouton « Tester UniFi Access » dans les réglages ; un code refusé par le lecteur (déjà pris, longueur) est signalé aux administrateurs.
- **Même code sur plusieurs sites** : le code peut être choisi à la main (4 à 8 chiffres) ; une même personne garde ainsi un seul code sur la Maison et la Grange.
- **Notifications par visite** : téléphones, journal seulement (niveau `info`) ou rien. Par défaut, une visite régulière va au journal (pas d'alerte à chaque passage).
- **Rappel** une fois, à 10 h, quand des passages réguliers s'arrêtent dans 7 jours ou moins (événement `visiteurs_fin_serie_proche`).
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

Événements : `visiteurs_debut`, `visiteurs_fin` (`id`, `nom`, `type`, `debut`, `fin`, `regulier`, `site`), `visiteurs_modifie`. Pour un passage régulier, ils sont émis à chaque passage, et `debut` / `fin` sont ceux du passage.

## Actions

`visiteurs.ajouter` (réponse : `id`, `code`, `message`), `visiteurs.modifier`, `visiteurs.terminer`, `visiteurs.supprimer`, `visiteurs.sauter`, `visiteurs.sejour`, `visiteurs.arrivee`, `visiteurs.reconnaitre_plaque` (réponse : `trouve`, `nom`, `type`, `id`).

Passages réguliers : `repetition_jours` (lundi … dimanche), `heure_debut`, `heure_fin` (une fin avant le début = jusqu'au lendemain), `toutes_les` (semaines, 1 à 12), `debut` (premier jour) et `jusqu_au` (dernier jour). `repetition_jours: []` dans `modifier` en refait une visite simple. `terminer` arrête le passage en cours (ou toute la série hors passage) ; `sauter` annule un passage (par défaut le prochain) ; `sejour` (`fin`, `debut` facultatif, ou `retirer: true`) ajoute ou annule une nuit sur place ; `supprimer` efface tous les passages. Une visite simple de passage qui reste dormir : `modifier` avec `type: sur_place` et un nouveau départ.

Agenda : les passages s'y affichent comme une série « chaque semaine » ; on peut en créer une depuis l'agenda (répétition hebdomadaire), supprimer un passage ou « ce passage et les suivants ».

Droits : comptes reliés à une personne (ou ceux choisis dans les options) et comptes de liaison (nom contenant « Liaison », pour la centrale), jamais une tablette murale. Les automatisations peuvent tout faire.

## Carte

```yaml
type: custom:visiteurs-card
mode: auto        # auto : tablette murale → accueil, sinon gestion ; ou gestion / accueil
title: Visiteurs
```

## Réglages

Depuis la carte (bouton ⚙️, administrateurs) ou les options de l'intégration : Wi-Fi invité (nom, mot de passe avec 🎲 générer, sécurité), consignes, lumière d'accueil, accès qu'un code peut ouvrir (on coche ensuite visite par visite), comportement pendant une visite, plage de nuit (22 h – 6 h), durées par défaut (passage 2 h, séjour 24 h), marges (30 min), qui prévenir et de quoi. Qui peut gérer les visites : options de l'intégration.

### Comportement pendant une visite (interrupteurs, lus par vos automatisations)

| Interrupteur | Par défaut |
|---|---|
| `switch.visiteurs_pause_armement_auto` — armement automatique suspendu pendant une visite | activé |
| `switch.visiteurs_invite_compte_present` — un invité sur place compte comme quelqu'un à la maison | activé |
| `switch.visiteurs_passage_en_simple_info` — passage de jour : personne détectée = simple info | activé |
| `switch.visiteurs_alerte_de_nuit_maintenue` — la nuit, personne détectée = alerte même en visite | activé |

Ils ne changent rien seuls : ce sont vos automatisations qui les lisent. Réservés aux administrateurs (un autre compte est refusé, même par l'API).

## Limites

- Le mot de passe du Wi-Fi invité est visible de tous les comptes (il est fait pour être donné) : ne pas y mettre celui du Wi-Fi principal.
- Le code visiteur est conservé lisible pour la famille (pour pouvoir le renvoyer) dans le stockage privé de Home Assistant, et haché pour la vérification.
- Passages réguliers : par semaine seulement (pas « le premier lundi du mois »). Un passage sauté ou arrêté disparaît de l'agenda.
- Codes visiteur : tablettes murales (comptes « TabDomo… ») et lecteurs UniFi Access. L'arrivée au lecteur n'est pas encore notée comme « arrivé·e ».

## Tests

`tests/test_visites.py` (fonctions pures, 16), `tests/bench_visiteurs.py` (108 contrôles + 5 après redémarrage, avec une imitation de l'API UniFi Access sur un vrai Home Assistant avec *Codes d'accès* 1.1), `tests/card_test.py` (49 contrôles dans Chromium : ordinateur, téléphone 380 px, tablette).
