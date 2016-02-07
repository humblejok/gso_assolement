'''
Created on 3 fevr. 2016

@author: humble_jok
'''
from assolement.models import Culture, Parcelle
from json import dumps
def compute(starting_year):

    parcelles = Parcelle.objects.filter(surface__gt=0.0)
    cultures = Culture.objects.filter(surface__gt=0)

    historique_cultures = {}

    for parcelle in parcelles:
        parcelle_key = parcelle.nom # TODO: Change to id after debug

        previous_culture = None

        for annee in parcelle.historique.filter(annee__lt=starting_year).order_by('annee'):
            culture_key = annee.culture.nom # TODO: Change to id after debug
            if not culture_key in historique_cultures:
                historique_cultures[culture_key] = {}
            if not parcelle_key in historique_cultures[culture_key]:
                historique_cultures[culture_key][parcelle_key] = []
            if not annee.annee in historique_cultures[culture_key][parcelle_key]:
                if -annee.annee in historique_cultures[culture_key][parcelle_key]:
                    historique_cultures[culture_key][parcelle_key].append(-annee.annee)
                historique_cultures[culture_key][parcelle_key].append(annee.annee)
            duree = int(annee.culture.duree_culture) # TODO: Clean when in prod
            retour = int(annee.culture.annees_retour)  # TODO: Clean when in prod
            if previous_culture==None or previous_culture.id!=annee.culture.id:
                if duree>1:
                    for index in range(1, duree):
                        if not parcelle.historique.filter(annee=annee.annee + index).exclude(culture=annee.culture).exists():
                            historique_cultures[culture_key][parcelle_key].append(annee.annee + index)
                for index in range(1, retour + 1):
                    if parcelle.historique.filter(annee=annee.annee + duree - 1 + index, culture=annee.culture).exists():
                        break
                    if -(annee.annee + duree - 1 + index) not in historique_cultures[culture_key][parcelle_key]:
                        historique_cultures[culture_key][parcelle_key].append(-(annee.annee + duree - 1 + index))
            previous_culture = annee.culture
        forbidden_cultures = Culture.objects.filter(sols_interdits=parcelle.type_de_sol) # TODO: Change to Q for "deconseille"
        for culture in forbidden_cultures:
            culture_key = culture.nom # TODO: Change to id after debug
            if culture_key not in historique_cultures:
                historique_cultures[culture_key] = {}
            if parcelle_key in historique_cultures[culture_key]:
                # TODO: Houston, we have a problem
                print "C'est pas possible!"
                print parcelle_key, culture_key
            historique_cultures[culture_key][parcelle_key] = []
            for year in reversed(range(-starting_year - 10, -starting_year+1)):
                if year not in historique_cultures[culture_key][parcelle_key] and -year not in historique_cultures[culture_key][parcelle_key]:
                    historique_cultures[culture_key][parcelle_key].append(year)
            print historique_cultures[culture_key][parcelle_key]


    current_cultures = {}

    for culture in cultures:
        culture_key = culture.nom
        if not culture_key in current_cultures:
            current_cultures[culture_key] = {'remaining_surface': culture.surface, 'parcelles': []}
        if culture_key in historique_cultures:
            for parcelle in historique_cultures[culture_key]:
                if starting_year in historique_cultures[culture_key][parcelle]:
                    effective_parcelle = Parcelle.objects.get(nom=parcelle)
                    current_cultures[culture_key]['remaining_surface'] -= effective_parcelle.surface
                    current_cultures[culture_key]['parcelles'].append(effective_parcelle.nom)
                    parcelles = parcelles.exclude(id=effective_parcelle.id)
                    if current_cultures[culture_key]['remaining_surface']<=0.0:
                        cultures = cultures.exclude(id=culture.id)
    available_parcelles = {}
    for culture in cultures:
        culture_key = culture.nom
        available_parcelles[culture_key] = []
        for parcelle in historique_cultures[culture_key]:
            if -starting_year in historique_cultures[culture_key]:
                continue
            if parcelles.filter(nom=parcelle).exists():
                available_parcelles[culture_key].append(parcelle)
    print available_parcelles
