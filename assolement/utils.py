'''
Created on 3 fevr. 2016

@author: humble_jok
'''
from assolement.models import Culture, Parcelle, Annee
from json import dumps
from ortools.constraint_solver import pywrapcp
import itertools

def make_int(fl_value):
    return int(fl_value * 1000.0)


def get_short_constraint(solver, label, culture, parcelle, year, forbid_previous_not_recommanded, forbid_soil_not_recommanded):
    already_assigned = parcelle.historique.filter(annee=year)
    if already_assigned.exists():
        already_assigned = already_assigned[0]
        if already_assigned.culture==culture:
            return solver.IntConst(1, label)
        else:
            return solver.IntConst(0, label)
    else:
        forbid = culture.sols_interdits.filter(id=parcelle.type_de_sol.id)
        not_reco = culture.sols_deconseilles.filter(id=parcelle.type_de_sol.id)
        if forbid.exists() or (forbid_soil_not_recommanded and not_reco.exists()):
            return solver.IntConst(0, label)
        previous = parcelle.historique.filter(annee=year-1)
        if previous.exists():
            previous = previous[0]
            forbid = culture.precedents_interdits.filter(id=previous.culture.id)
            not_reco = culture.precedents_deconseilles.filter(id=previous.culture.id)
            if forbid.exists() or (forbid_previous_not_recommanded and not_reco.exists()):
                return solver.IntConst(0, label)
        if culture.annees_retour>0:
            for back_index in range(1, culture.annees_retour + 1):
                previous = parcelle.historique.filter(annee=year-back_index, culture__id=culture.id)
                if previous.exists():
                    return solver.IntConst(0, label)
        return solver.IntVar(0,1, label)

def get_culture_long_constraints(culture_info, db_parcelles, c_min_surfaces, c_max_surfaces):
    culture_solver = pywrapcp.Solver("SUB")
    culture_surfaces = []
    culture_forced = []
    for p_idx in culture_info['db_parcelles']:
        culture_surfaces.append(make_int(db_parcelles[p_idx].surface))
        culture_forced.append(culture_solver.IntVar(0,1, 'c_%i_f_%i' % (culture_info['c_idx'], p_idx)))
    culture_solver.Add(culture_solver.ScalProd(culture_forced, culture_surfaces)==culture_solver.IntVar(0, c_max_surfaces[culture_info['c_idx']], 'c_surface_%i' % culture_info['c_idx']))
    f_solution = culture_solver.Assignment()
    f_solution.Add(culture_forced)
    f_phase = culture_solver.Phase(culture_forced, culture_solver.INT_VAR_SIMPLE, culture_solver.ASSIGN_MAX_VALUE)
    culture_solver.NewSearch(f_phase)
    all_solutions = []
    all_valid_solutions = []
    while culture_solver.NextSolution():
        forced_parcelles = [culture_info['db_parcelles'][index] for index in range(0, len(culture_info['db_parcelles'])) if culture_forced[index].Value()==1]
        all_solutions.append(forced_parcelles)
        surface = 0
        for p_idx in forced_parcelles:
            surface += make_int(db_parcelles[p_idx].surface)
        if surface>c_min_surfaces[culture_info['c_idx']]:
            all_valid_solutions.append(forced_parcelles)
    culture_solver.EndSearch()
    return (all_valid_solutions, True) if len(all_valid_solutions)>0 else (all_solutions, False)

def get_long_constraints(db_parcelles, cultures, c_min_surfaces, c_max_surfaces, year):
    constraints = {}
    p_idx = 0
    long_cultures = {}
    for parcelle in db_parcelles:
        previous = parcelle.historique.filter(annee=year-1, culture__duree_culture__gt=1)
        if previous.exists():
            culture = previous[0].culture
            c_idx = cultures.index(culture.id)
            count = 0
            for working_year in reversed(range(year-culture.duree_culture, year)):
                previous = parcelle.historique.filter(annee=working_year, culture__id=culture.id)
                if previous.exists():
                    count += 1
                else:
                    break
            if count>0 and count<culture.duree_culture:
                if culture.id not in long_cultures:
                    long_cultures[culture.id] = {'db_parcelles': [], 'surface': 0, 'culture': culture, 'c_idx': c_idx}
                long_cultures[culture.id]['db_parcelles'].append(p_idx)
                long_cultures[culture.id]['surface'] += make_int(parcelle.surface)
        p_idx += 1
    for culture_id in long_cultures:
        if long_cultures[culture_id]['surface']>c_max_surfaces[long_cultures[culture.id]['c_idx']]:
            constraints[long_cultures[culture.id]['c_idx']] = []
            all_alternatives = get_culture_long_constraints(long_cultures[culture.id], db_parcelles, c_min_surfaces, c_max_surfaces)
            for alternative in all_alternatives[0]:
                sub_constraints = {}
                for p_idx in range(0, len(db_parcelles)):
                    if p_idx in alternative:
                        sub_constraints[(long_cultures[culture.id]['c_idx'], p_idx)] = 1
                    elif all_alternatives[1]:
                        sub_constraints[(long_cultures[culture.id]['c_idx'], p_idx)] = 0
                constraints[long_cultures[culture.id]['c_idx']].append(sub_constraints)
        else:
            sub_constraints = {}
            for p_idx in long_cultures[culture.id]['db_parcelles']:
                sub_constraints[(long_cultures[culture.id]['c_idx'], p_idx)] = 1
            constraints[long_cultures[culture.id]['c_idx']] = [sub_constraints]
    return constraints

def assolement_computer(working_year):
    solutions = {}
    
    db_parcelles = Parcelle.objects.filter(surface__gt=0.0).order_by('nom')
    db_cultures = Culture.objects.filter(surface__gt=0.0).order_by('nom')
    cultures = [culture.id for culture in db_cultures]
    parcelles = [parcelle.id for parcelle in db_parcelles]
    
    p_surfaces = [make_int(parcelle.surface) for parcelle in db_parcelles]
    
    c_range = range(0, len(cultures))
    p_range = range(0, len(parcelles))
    
    c_min_surfaces = [make_int(culture.surface * (1.0 - (culture.tolerance / 100.0))) for culture in db_cultures]
    # c_max_surfaces = [make_int(culture.surface * (1.0 + (culture.tolerance / 100.0))) for culture in db_cultures]
    c_max_surfaces = [make_int(culture.surface * (1.0 + (culture.tolerance / 100.0))) for culture in db_cultures]
    
    long_constraints = get_long_constraints(db_parcelles, cultures, c_min_surfaces, c_max_surfaces, working_year)
    num_solutions = 0
    # solver_type: 2 = CHOOSE_FIRST_UNBOUND, 1 = INT_VAR_SIMPLE
    # solver_type: 3 = ASSIGN_MAX_VALUE, 5 = ASSIGN_CENTER_VALUE
    for force_mandatory in [True, False]:
        for previous_reco in [True, False]:
            for soil_reco in [True, False]:
                for constraints in itertools.product(*long_constraints.values()):    
                    solver = pywrapcp.Solver('Assolement ' + str(working_year))
                    cultures_assignments = {}
                    cultures_assignments_as_list = []
                    objectives = []
                    # Assigning defaults
                    for c_idx in c_range:
                        for p_idx in p_range:
                            cultures_assignments[(c_idx, p_idx)] = get_short_constraint(solver, 'c_%i_p_%i' % (c_idx, p_idx), db_cultures[c_idx], db_parcelles[p_idx], working_year, previous_reco, soil_reco)
                    for assigments in constraints:
                        for key in assigments:
                            cultures_assignments[key] = solver.IntConst(assigments[key], 'c_%i_p_%i' % key)
                    # No culture or only one culture per parcelle
                    for p_idx in p_range:
                        solver.Add(solver.Sum([cultures_assignments[(c_idx, p_idx)] for c_idx in c_range])<=1)
                    # Assign constraints
                    for c_idx in c_range:
                        c_surface = solver.IntVar(c_min_surfaces[c_idx] if db_cultures[c_idx].obligatoire and force_mandatory else 0, c_max_surfaces[c_idx], 'c_surface_%i' % c_idx)
                        objectives.append(solver.Maximize(c_surface, 1000))
                        solver.Add(solver.ScalProd([cultures_assignments[(c_idx, p_idx)] for p_idx in p_range], p_surfaces)==c_surface)
                    # Convert to list
                    for c_idx in c_range:
                        for p_idx in p_range:
                            cultures_assignments_as_list.append(cultures_assignments[(c_idx, p_idx)])
                            
                    
                            
                    solution = solver.Assignment()
                    solution.Add(cultures_assignments_as_list)
                    
                    phase = solver.Phase(cultures_assignments_as_list, solver.CHOOSE_FIRST_UNBOUND, solver.ASSIGN_MAX_VALUE)
                    solver.NewSearch(phase, objectives)
            
                    while solver.NextSolution():
                        solutions[num_solutions] = {}
                        print "SOLUTION NO:", num_solutions
                        for c_idx in c_range:
                            solutions[num_solutions][cultures[c_idx]] = {'allocation': [], 'allocated_surface': 0.0, 'match': False}
                            for p_idx in p_range:
                                solutions[num_solutions][cultures[c_idx]]['allocated_surface'] += db_parcelles[p_idx].surface * cultures_assignments[(c_idx, p_idx)].Value()
                                if cultures_assignments[(c_idx, p_idx)].Value()==1:
                                    solutions[num_solutions][cultures[c_idx]]['allocation'].append(parcelles[p_idx])
                            culture = db_cultures[c_idx]
                            solutions[num_solutions][cultures[c_idx]]['match'] = solutions[num_solutions][cultures[c_idx]]['allocated_surface']>=(culture.surface * (1.0 - (culture.tolerance / 100.0))) and solutions[num_solutions][cultures[c_idx]]['allocated_surface']<=(culture.surface * (1.0 + (culture.tolerance / 100.0)))
                        for solution_key in solutions:
                            if solution_key!=num_solutions:
                                if cmp(solutions[solution_key], solutions[num_solutions])==0:
                                    del solutions[num_solutions]
                                    num_solutions -= 1
                                    break
                        num_solutions += 1
                    print("num_solutions: ", num_solutions)
                    print('failures:', solver.Failures())
                    print('branches:', solver.Branches())
                    print('WallTime:', solver.WallTime())
                    print solutions
    
    return solutions