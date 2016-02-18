'''
Created on 3 fevr. 2016

@author: humble_jok
'''
from assolement.models import Culture, Parcelle, Annee
from json import dumps
from ortools.constraint_solver import pywrapcp

def make_int(fl_value):
    return int(fl_value * 1000.0)

def assolement_compute(working_year):
    solver = pywrapcp.Solver('Assolement ' + str(working_year))
    db_parcelles = Parcelle.objects.filter(surface__gt=0.0).order_by('nom')
    db_cultures = Culture.objects.filter(surface__gt=0.0).order_by('nom')[0:3]
    cultures = [culture.id for culture in db_cultures]
    parcelles = [parcelle.id for parcelle in db_parcelles]
    p_surfaces = [make_int(parcelle.surface) for parcelle in db_parcelles]
    
    c_range = range(0, len(cultures))
    p_range = range(0, len(parcelles))
    
    c_min_surfaces = [make_int(culture.surface * (1.0 - (culture.tolerance / 100.0))) for culture in db_cultures]
    c_max_surfaces = [make_int(culture.surface * (1.0 + (culture.tolerance / 100.0))) for culture in db_cultures]
    
    cultures_assignments = {}
    cultures_assignments_as_list = []
    for c_idx in c_range:
        for p_idx in p_range:
            cultures_assignments[(c_idx, p_idx)] = solver.IntVar(0,1, 'c_%i_p_%i' % (c_idx, p_idx))
            cultures_assignments_as_list.append(cultures_assignments[(c_idx, p_idx)])
    # Rien ou une seule culture par parcelle
    for p_idx in p_range:
        solver.Add(solver.Sum([cultures_assignments[(c_idx, p_idx)] for c_idx in c_range])<=1)
    # La surface cultivee est dans le range
    for c_idx in c_range:
        c_surface = solver.IntVar(c_min_surfaces[c_idx], c_max_surfaces[c_idx], 'c_surface_%i' % c_idx)
        solver.Add(solver.ScalProd([cultures_assignments[(c_idx, p_idx)] for p_idx in p_range], p_surfaces)==c_surface)
        forbidden_parcelles = []
        forced_parcelles = []
        for p_idx in p_range:
            if db_cultures[c_idx].sols_interdits.filter(id=db_parcelles[p_idx].type_de_sol.id).exists():
                forbidden_parcelles.append(p_idx)
            elif db_cultures[c_idx].sols_deconseilles.filter(id=db_parcelles[p_idx].type_de_sol.id).exists():
                # forbidden_parcelles.append(p_idx)
                None
            elif db_cultures[c_idx].duree_culture>1:
                count = 0
                for year in reversed(range(working_year-db_cultures[c_idx].duree_culture, working_year)):
                    previous = db_parcelles[p_idx].historique.filter(annee=year)
                    if previous.exists():
                        if previous[0].culture.id==db_cultures[c_idx].id:
                            count += 1
                        else:
                            break
                    else:
                        break
                if count>0 and count<db_cultures[c_idx].duree_culture:
                    forced_parcelles.append(p_idx)
                    continue
            if db_cultures[c_idx].precedents_interdits.count()>0 and db_parcelles[p_idx].historique.filter(annee=working_year-1, culture__in=db_cultures[c_idx].precedents_interdits.all()).exists():
                forbidden_parcelles.append(p_idx)
            elif db_cultures[c_idx].precedents_deconseilles.count()>0 and db_parcelles[p_idx].historique.filter(annee=working_year-1, culture__in=db_cultures[c_idx].precedents_deconseilles.all()).exists():
                # forbidden_parcelles.append(p_idx)
                None
        for p_idx in forbidden_parcelles:
            print db_cultures[c_idx].nom, db_cultures[c_idx].surface, 'CANNOT', db_parcelles[p_idx].nom
            solver.Add(cultures_assignments[(c_idx, p_idx)]==0)
        for p_idx in forced_parcelles:
            print db_cultures[c_idx].nom, db_cultures[c_idx].surface, 'MUST', db_parcelles[p_idx].nom
            solver.Add(cultures_assignments[(c_idx, p_idx)]==1)
        
    
    solution = solver.Assignment()
    solution.Add(cultures_assignments_as_list)
    collector = solver.AllSolutionCollector(solution)
    phase = solver.Phase(cultures_assignments_as_list, solver.INT_VAR_SIMPLE, solver.INT_VALUE_SIMPLE)
    solver.Solve(phase, [collector])
    num_solutions = collector.SolutionCount()
    print("num_solutions: ", num_solutions)
    print('failures:', solver.Failures())
    print('branches:', solver.Branches())
    print('WallTime:', solver.WallTime())
    
def _assolement_compute(working_year):
    solver = pywrapcp.Solver('Assolement ' + str(working_year))
    db_parcelles = Parcelle.objects.filter(surface__gt=0.0).order_by('nom')
    db_cultures = Culture.objects.filter(surface__gt=0.0).order_by('nom')
    parcelles = [parcelle.id for parcelle in db_parcelles]
    cultures = [-1] + [culture.id for culture in db_cultures]
    print parcelles
    print cultures
    
    p_surfaces = [solver.IntVar(0, make_int(parcelle.surface), 'surface_%i' % parcelle.id) for parcelle in db_parcelles]
    
    p_assignments = [solver.IntVar(0, len(cultures), 'parcelle_%i' % i) for i in range(len(parcelles))]
    
    c_min_surfaces = [0] + [make_int(culture.surface * (1.0 - (culture.tolerance / 100.0))) for culture in db_cultures]
    c_max_surfaces = [1000000000] + [make_int(culture.surface * (1.0 + (culture.tolerance / 100.0))) for culture in db_cultures]
    
    for c_idx in range(1, len(cultures)):
        c_surface = solver.IntVar(c_min_surfaces[c_idx], c_max_surfaces[c_idx], 'c_surface_%i' % c_idx)
        c_sum = solver.Sum([p_surfaces[p_id] for p_id in range(len(parcelles)) if p_assignments[p_id]==c_idx])
        print c_idx, c_sum
        solver.Add(c_sum==c_surface)
    
    solution = solver.Assignment()
    solution.Add(p_assignments)
    collector = solver.AllSolutionCollector(solution)
    phase = solver.Phase(p_assignments, solver.INT_VAR_SIMPLE, solver.INT_VALUE_SIMPLE)
    solver.Solve(phase, [collector])
    num_solutions = collector.SolutionCount()
    print("num_solutions: ", num_solutions)
    print('failures:', solver.Failures())
    print('branches:', solver.Branches())
    print('WallTime:', solver.WallTime())
    
    
def or_compute(working_year):
    solver = pywrapcp.Solver('Assolement ' + str(working_year))
    authorized = {}
    cultures = Culture.objects.filter(surface__gt=0.0)
    for culture in cultures:
        authorized[culture.id] = [parcelle.id for parcelle in Parcelle.objects.filter(surface__gt=0.0).exclude(type_de_sol__in=culture.sols_interdits.all())]
    surfaces = {}
    parcelles_ids = []
    used = []
    surfaces_array = []
    for parcelle in Parcelle.objects.filter(surface__gt=0.0).order_by('nom'):
        surfaces[parcelle.id] = solver.IntVar(0, make_int(parcelle.surface), 'Surface_%i' % parcelle.id)
        surfaces_array.append(make_int(parcelle.surface))
        parcelles_ids.append(parcelle.id)
        used.append(solver.IntVar(0,1, "Parcelle_%i" % parcelle.id))
    total_surfaces = solver.IntVar(0, sum(surfaces), 'total_surfaces')
    solver.Add(total_surfaces == solver.ScalProd(used, surfaces_array))
    for culture in cultures:
        crop = solver.Sum([surfaces[p_id] for p_id in authorized[culture.id]])
        solver.Add(crop<=make_int(culture.surface * (1.0 + (culture.tolerance / 100.0))))
        solver.Add(crop>=make_int(culture.surface * (1.0 - (culture.tolerance / 100.0))))
        
    objective = solver.Maximize(total_surfaces, 1)
    db = solver.Phase(used, solver.CHOOSE_FIRST_UNBOUND, solver.ASSIGN_MAX_VALUE)
    solver.NewSearch(db, [objective])
    while solver.NextSolution():
        print "Total Surface", total_surfaces.Value()
        for p_id in parcelles_ids:
            if used[p_id] == 1:
                print Parcelle.objects.get(id=p_id), used[p_id]
    solver.EndSearch()
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
                    historique_cultures[culture_key][parcelle_key].remove(-annee.annee)
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
                    current_cultures[culture_key]['parcelles'].append(effective_parcelle)
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
                available_parcelles[culture_key].append(parcelles.get(nom=parcelle))
                available_parcelles[culture_key] = sorted(available_parcelles[culture_key], key = lambda p: p.surface, reverse = True)
    print available_parcelles
    no_solution = False
    
    # Ordering by number of possibilities
    culture_keys = available_parcelles.keys()
    culture_keys = sorted(culture_keys, key = lambda c: len(available_parcelles[c]), reverse = False)
    

    while len(cultures)>0 and not no_solution:
        culture = cultures.get(nom=culture_keys[0])
        culture_key = culture_keys[0]
        shift = culture.surface * culture.tolerance / 100.0
        while len(available_parcelles[culture_key])!=0 and abs(current_cultures[culture_key]["remaining_surface"])>shift:
            passed_all = True
            for selected_parcelle in available_parcelles[culture_key]:
                if selected_parcelle.surface + shift<=current_cultures[culture_key]["remaining_surface"] or abs(current_cultures[culture_key]["remaining_surface"] - selected_parcelle.surface)<=shift:
                    passed_all = False
                    break
            if passed_all:
                selected_parcelle = available_parcelles[culture_key][-1]
            for sub_culture_key in available_parcelles:
                if selected_parcelle in available_parcelles[sub_culture_key]:
                    available_parcelles[sub_culture_key].remove(selected_parcelle)
            current_cultures[culture_key]["remaining_surface"] -= selected_parcelle.surface
            current_cultures[culture_key]["parcelles"].append(selected_parcelle)
        cultures = cultures.exclude(id=culture.id)
        culture_keys.remove(culture_key)
        print len(cultures)
    print current_cultures
    for culture_key in current_cultures:
        information = current_cultures[culture_key]
        for parcelle in information['parcelles']:
            annee = Annee()
            annee.culture = Culture.objects.get(nom=culture_key)
            annee.annee = starting_year
            annee.save()
            if parcelle.historique.filter(annee=starting_year).exists():
                old_annee = parcelle.historique.get(annee=starting_year)
                parcelle.historique.remove(old_annee)
                old_annee.delete()
            parcelle.historique.add(annee)
            parcelle.save()
