// Liste des offres suivies.
// Pour ajouter une offre : copie un bloc { ... }, change l'id (unique) et les champs, puis commit.
//
// type     : "ens" (enseignement / EC) · "pd" (postdoc) · "ds" (data scientist) · "da" (data analyst)
// fit      : "hi" (très bon) · "mid" (correct) · "lo" (partiel)
// deadline : "AAAA-MM-JJ" ou null si aucune date limite affichée
// published: "AAAA-MM-JJ" ou null

window.OFFRES = [
  {
    id: "cesi-pau",
    type: "ens", fit: "hi",
    org: "CESI LINEACT",
    title: "Enseignant-chercheur IA, science des données et aide à la décision",
    location: "Pau (64)",
    contract: "CDI · jusqu'à 38 k€/an",
    deadline: null, published: "2026-09-17",
    why: "Axes explicitement « IA explicable et de confiance » et analyse prédictive. Qualification CNU 27 exigée : tu l'as. Tu connais le labo de l'intérieur.",
    contact: "",
    url: "https://lineact.cesi.fr/recrutement/enseignant-chercheur-en-intelligence-artificielle-science-des-donnees-et-systemes-daide-a-la-decision-hf-fr/"
  },
  {
    id: "oniris-cerc",
    type: "ens", fit: "hi",
    org: "Oniris VetAgroBio",
    title: "Chargé d'enseignement et de recherche contractuel en sciences des données",
    location: "Nantes (44)",
    contract: "CDD 8 mois · dès 2 130 € net/mois · début 01/01/2027",
    deadline: "2026-11-04", published: "2026-10-14",
    why: "Équipe StatSC (classification, réduction de dimension, multiblocs) : colle à IDFC et au feature clustering robuste. Date passée, mais un mail direct à la responsable d'équipe peut encore passer.",
    contact: "veronique.cariou@oniris-nantes.fr",
    url: "https://www.sfds.asso.fr/sdoc-15418-a307bb0ec9ae5dc4ba29ca3ead52e904-2026_fiche_annonce_cerc_msi.pdf"
  },
  {
    id: "sncf-maint",
    type: "ds", fit: "hi",
    org: "SNCF Réseau",
    title: "Ingénieur Data Science – Maintenance prédictive ferroviaire",
    location: "Saint-Denis-de-Palin (18)",
    contract: "CDI",
    deadline: null, published: "2026-11-02",
    why: "Cœur de ton expertise : maintenance prédictive, modèles de durée, fiabilité et vieillissement des actifs. Vérifier le lieu exact sur le site carrière SNCF.",
    contact: "",
    url: "https://www.ziprecruiter.fr/jobs/638383011-ingenieur-ou-ingenieure-data-science-maintenance-predictive-ferroviaire-a-sncf"
  },
  {
    id: "cnam-shom",
    type: "pd", fit: "hi",
    org: "CNAM",
    title: "Postdoc – Classification dynamique de données fonctionnelles (SHOM)",
    location: "Paris 3e",
    contract: "CDD 15 mois",
    deadline: null, published: "2026-09-21",
    why: "Classification et séries temporelles, dans ton établissement. Démarrage prévu sept./oct. : demander si le poste est encore ouvert.",
    contact: "feriel.bouhadjera@lecnam.net",
    url: "https://audigier.perso.math.cnrs.fr/2026/offre_postdoc_shom.pdf"
  },
  {
    id: "cnam-lait",
    type: "pd", fit: "mid",
    org: "CNAM CEDRIC",
    title: "Postdoc – Analyse prédictive de la qualité du lait (données fonctionnelles)",
    location: "Paris 3e",
    contract: "CDD 16 mois",
    deadline: null, published: "2026-09-16",
    why: "Données fonctionnelles et multiniveaux, même labo que toi. Démarrage prévu en septembre : vérifier s'il est encore ouvert.",
    contact: "vincent.audigier@cnam.fr",
    url: "https://audigier.perso.math.cnrs.fr/2026/PostDoc_camelait4med.pdf"
  },
  {
    id: "cesi-nanterre",
    type: "ens", fit: "mid",
    org: "CESI LINEACT",
    title: "Enseignant-chercheur IoT et systèmes cyber-physiques sécurisés",
    location: "Nanterre / La Défense (92)",
    contract: "CDI",
    deadline: null, published: "2026-10-09",
    why: "Profil IoT/sécurité, mais en Île-de-France. Angle possible : données capteurs et maintenance prédictive sur systèmes cyber-physiques.",
    contact: "",
    url: "https://lineact.cesi.fr/recrutement/enseignant-chercheur-en-internet-des-objets-et-systemes-cyber-physiques-securises-hf-fr"
  },
  {
    id: "asnr-bayes",
    type: "pd", fit: "mid",
    org: "ASNR",
    title: "Postdoc – Modèles de mélange bayésiens spatio-temporels",
    location: "Fontenay-aux-Roses (92)",
    contract: "CDD 12 mois renouvelable · début déc. 2026",
    deadline: null, published: "2026-10-19",
    why: "Statistique bayésienne sur données longitudinales, proche de chez toi. Attendus : inférence bayésienne, analyse d'images, C++.",
    contact: "sophie.ancelet@asnr.fr",
    url: "https://www.sfds.asso.fr/sdoc-15433-e32956074c20281838a53a7017f2b782-postdocradioaide_ancelet.pdf"
  },
  {
    id: "um6p-llm",
    type: "pd", fit: "mid",
    org: "UM6P (Maroc)",
    title: "Postdoc – LLM pour la maintenance prédictive",
    location: "Benguerir, Maroc",
    contract: "Postdoc",
    deadline: null, published: "2026-06-22",
    why: "Maintenance prédictive et séries temporelles comptent comme un « strong plus ». Point faible : ils attendent une thèse orientée LLM.",
    contact: "",
    url: "https://academicpositions.com/ad/mohammed-vi-polytechnic-university/2026/gti-postdoc-postdoctoral-researchers-in-artificial-intelligence-ai-focus-on-large-language-models-llms-for-predictive-maintenance/236847"
  },
  {
    id: "cdc-da",
    type: "da", fit: "mid",
    org: "Caisse des Dépôts",
    title: "Data analyst – DCBP",
    location: "Paris",
    contract: "Catégorie A · titulaires et contractuels",
    deadline: null, published: "2026-10-19",
    why: "Pilotage et performance bancaire : moins scientifique, mais stable, télétravail jusqu'à 3 j/sem. Ces offres sont dépubliées sans préavis.",
    contact: "",
    url: "https://choisirleservicepublic.gouv.fr/offre-emploi/data-analyst---dcbp-reference-2026-2445207/"
  },
  {
    id: "drees-sante",
    type: "da", fit: "mid",
    org: "DREES",
    title: "Data analyst – Santé de la population et parcours de soins",
    location: "Paris",
    contract: "Fonction publique d'État",
    deadline: null, published: "2026-10-23",
    why: "Statistique publique, études et publications : ton profil de statisticien ENSAE y est bien lu.",
    contact: "",
    url: "https://choisirleservicepublic.gouv.fr/offre-emploi/data-analyst-sur-la-sante-de-la-population-et-les-parcours-de-soins-reference-2026-2449479/"
  },
  {
    id: "octopus-rd",
    type: "ds", fit: "mid",
    org: "Octopus IT (cabinet)",
    title: "Data Scientist – R&D PhD",
    location: "Paris",
    contract: "CDI · 45–50 k€",
    deadline: null, published: "2026-10-25",
    why: "Poste R&D qui cible explicitement les docteurs. L'annonce se retrouve sur Hellowork.",
    contact: "",
    url: "https://www.hellowork.com/fr-fr/emploi/metier_data-scientist-ville_paris-75000.html"
  },
  {
    id: "inserm-epi",
    type: "pd", fit: "lo",
    org: "Inserm",
    title: "Postdoc – Épidémiologie environnementale et infections",
    location: "Paris",
    contract: "CDD 24 mois · début janv. 2027",
    deadline: null, published: "2026-10-14",
    why: "Exposition météo à court terme et hospitalisations : séries temporelles, mais domaine éloigné.",
    contact: "laurence.watier@inserm.fr",
    url: "https://www.sfds.asso.fr/sdoc-15421-2c30af16369dc36358440545f90cf58e-postdoctoral_position_in_environmental_epidemiology_and_infectious_diseases_in_paris.pdf"
  },
  {
    id: "edf-ds",
    type: "ds", fit: "lo",
    org: "EDF",
    title: "Data Scientist (réf. 2026-174432)",
    location: "Saint-Denis (93)",
    contract: "CDI · ~46 k€",
    deadline: null, published: "2026-10-10",
    why: "Demande 6 ans de déploiement en production : décalé, mais EDF recrute souvent. À garder en veille.",
    contact: "",
    url: "https://www.edf.fr/edf-recrute/offre/detail/2026-174432"
  }
];
