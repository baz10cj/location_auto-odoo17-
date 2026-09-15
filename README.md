# location_auto-odoo17

Module Odoo 17 pour la gestion d'une agence de location automobile : états des lieux, réservations, contrats, portail client et support en ligne.

## Fonctionnalités

- **Véhicules** : gestion de la flotte (marque, modèle, immatriculation, état, tarifs).
- **Réservations** : cycle complet de la demande à la validation, avec suivi par statut.
- **Contrats de location** : génération de contrats PDF signature électronique côté portail.
- **États des lieux** : gestion des inspections avant / après location.
- **Portail client** : espace personnel avec réservations, contrats, factures, inspections et documents.
- **Site web** : catalogue de véhicules public et page de réservation.
- **Support** : tickets de support client depuis le site avec conversation temps réel (`bus`).
- **Paiement** : paiement en ligne via Stripe (`payment_stripe`).

## Dépendances

Module Odoo principaux requis :

```
base, mail, portal, website, account, bus, payment, payment_stripe, account_payment
```

## Installation

1. Copier le module dans un dossier d'addons Odoo.
2. Ajouter le chemin dans `addons_path` de la configuration Odoo.
3. Activer le mode développeur, puis installer le module `location_auto` depuis Applications.

Le module installe automatiquement le layout de rapport Keydrive au démarrage.

## Modèles principaux

| Modèle                  | Description                         |
| ----------------------- | ----------------------------------- |
| `la.vehicle`            | Flotte de véhicules                |
| `la.reservation`        | Réservations                       |
| `la.contract`           | Contrats de location               |
| `location.etat.lieux`   | États des lieux / inspections      |
| `la.support.ticket`     | Tickets de support                 |
| `res.partner`           | Clients et documents étendus       |

## Données de démonstration

`data/mock_data.xml` contient des données fictives (clients, contrats) à des fins de démonstration.

## Licence

Ce module est sous licence **LGPL-3**.

Copyright — location_auto (nom technique conservé dans les descriptions).