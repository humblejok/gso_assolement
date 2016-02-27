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
    culture_solver.Add(culture_solver.ScalProd(culture_forced, culture_surfaces)==culture_solver.IntVar(c_min_surfaces[culture_info['c_idx']], c_max_surfaces[culture_info['c_idx']], 'c_surface_%i' % culture_info['c_idx']))
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
    return all_valid_solutions if len(all_valid_solutions)>0 else all_solutions

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
            for alternative in all_alternatives:
                sub_constraints = {}
                for p_idx in alternative:
                    sub_constraints[(long_cultures[culture.id]['c_idx'], p_idx)] = 1
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
                        c_surface = solver.IntVar(c_min_surfaces[c_idx] if db_cultures[c_idx].obligatoire and force_mandatory else 0, c_max_surfaces[c_idx], 'c_surface_%i' % c_idx)
                        objectives.append(solver.Maximize(c_surface, 1000))
                        solver.Add(solver.ScalProd([cultures_assignments[(c_idx, p_idx)] for p_idx in p_range], p_surfaces)==c_surface)
                    for assigments in constraints:
                        for key in assigments:
                            cultures_assignments[key] = solver.IntConst(assigments[key], 'c_%i_p_%i' % key)
                    # No culture or only one culture per parcelle
                    for p_idx in p_range:
                        solver.Add(solver.Sum([cultures_assignments[(c_idx, p_idx)] for c_idx in c_range])<=1)        
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
        
def assolement_maximize(working_year):
    solutions = {}
    solver = pywrapcp.Solver('Assolement ' + str(working_year))
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
    
    cultures_assignments = {}
    cultures_assignments_as_list = []
    for c_idx in c_range:
        for p_idx in p_range:
            cultures_assignments[(c_idx, p_idx)] = solver.IntVar(0,1, 'c_%i_p_%i' % (c_idx, p_idx))
    objectives = []
    # La surface cultivee est dans le range
    for c_idx in c_range:
        c_surface = solver.IntVar(0, c_max_surfaces[c_idx], 'c_surface_%i' % c_idx)
        forbidden_parcelles = []
        forced_parcelles = []
        forced_surface = 0.0
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
                    forced_surface += make_int(db_parcelles[p_idx].surface)
                    continue
            if db_cultures[c_idx].precedents_interdits.count()>0 and db_parcelles[p_idx].historique.filter(annee=working_year-1, culture__in=db_cultures[c_idx].precedents_interdits.all()).exists():
                forbidden_parcelles.append(p_idx)
            elif db_cultures[c_idx].precedents_deconseilles.count()>0 and db_parcelles[p_idx].historique.filter(annee=working_year-1, culture__in=db_cultures[c_idx].precedents_deconseilles.all()).exists():
                # forbidden_parcelles.append(p_idx)
                None
        for p_idx in forbidden_parcelles:
            # print db_cultures[c_idx].nom, db_cultures[c_idx].surface, 'CANNOT', db_parcelles[p_idx].nom
            cultures_assignments[(c_idx, p_idx)] = solver.IntConst(0, 'c_%i_p_%i' % (c_idx, p_idx))
        print forced_surface, c_max_surfaces[c_idx]
        if forced_surface>c_max_surfaces[c_idx]:
            print db_cultures[c_idx].nom, db_cultures[c_idx].surface, forced_surface, "MUST CANCEL ONE OR MANY"
            culture_solver = pywrapcp.Solver("SUB")
            culture_surfaces = []
            culture_forced = []
            for p_idx in forced_parcelles:
                culture_surfaces.append(p_surfaces[p_idx])
                culture_forced.append(culture_solver.IntVar(0,1, 'c_%i_f_%i' % (c_idx, p_idx)))
            culture_solver.Add(culture_solver.ScalProd(culture_forced, culture_surfaces)==culture_solver.IntVar(c_min_surfaces[c_idx], c_max_surfaces[c_idx], 'c_surface_%i' % c_idx))
            f_solution = culture_solver.Assignment()
            f_solution.Add(culture_forced)
            f_phase = culture_solver.Phase(culture_forced, culture_solver.INT_VAR_SIMPLE, culture_solver.ASSIGN_RANDOM_VALUE)
            culture_solver.NewSearch(f_phase)
            while culture_solver.NextSolution():
                forced_parcelles = [forced_parcelles[index] for index in range(0, len(forced_parcelles)) if culture_forced[index].Value()==1]
                print "FOUND CANCEL", forced_parcelles
                break
            culture_solver.EndSearch()
        for p_idx in forced_parcelles:
            print db_cultures[c_idx].nom, db_cultures[c_idx].surface, 'MUST', db_parcelles[p_idx].nom,db_parcelles[p_idx].surface 
            for sub_c_idx in c_range:
                cultures_assignments[(c_idx, p_idx)] = solver.IntConst(1 if sub_c_idx==c_idx else 0, 'c_%i_p_%i' % (c_idx, p_idx))
        solver.Add(solver.ScalProd([cultures_assignments[(c_idx, p_idx)] for p_idx in p_range], p_surfaces)==c_surface)
        objectives.append(solver.Maximize(c_surface, 1000))
    # Rien ou une seule culture par parcelle
    for p_idx in p_range:
        solver.Add(solver.Sum([cultures_assignments[(c_idx, p_idx)] for c_idx in c_range])<=1)        
    # Convert to list
    for c_idx in c_range:
        for p_idx in p_range:
            cultures_assignments_as_list.append(cultures_assignments[(c_idx, p_idx)])
    solution = solver.Assignment()
    solution.Add(cultures_assignments_as_list)
    phase = solver.Phase(cultures_assignments_as_list, solver.CHOOSE_FIRST_UNBOUND, solver.ASSIGN_MAX_VALUE)
    solver.NewSearch(phase, objectives)
    num_solutions = 0
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
        num_solutions += 1
    print("num_solutions: ", num_solutions)
    print('failures:', solver.Failures())
    print('branches:', solver.Branches())
    print('WallTime:', solver.WallTime())
    print solutions
    return solutions

def assolement_compute(working_year):
    solver = pywrapcp.Solver('Assolement ' + str(working_year))
    db_parcelles = Parcelle.objects.filter(surface__gt=0.0).order_by('nom')
    db_cultures = Culture.objects.filter(surface__gt=0.0).order_by('nom')
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
    # La surface cultivee est dans le range
    for c_idx in c_range:
        print db_cultures[c_idx].nom, db_cultures[c_idx].surface
        c_surface = solver.IntVar(c_min_surfaces[c_idx], c_max_surfaces[c_idx], 'c_surface_%i' % c_idx)
        forbidden_parcelles = []
        forced_parcelles = []
        forced_surface = 0.0
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
                    forced_surface += make_int(db_parcelles[p_idx].surface)
                    continue
            if db_cultures[c_idx].precedents_interdits.count()>0 and db_parcelles[p_idx].historique.filter(annee=working_year-1, culture__in=db_cultures[c_idx].precedents_interdits.all()).exists():
                forbidden_parcelles.append(p_idx)
            elif db_cultures[c_idx].precedents_deconseilles.count()>0 and db_parcelles[p_idx].historique.filter(annee=working_year-1, culture__in=db_cultures[c_idx].precedents_deconseilles.all()).exists():
                # forbidden_parcelles.append(p_idx)
                None
        for p_idx in forbidden_parcelles:
            # print db_cultures[c_idx].nom, db_cultures[c_idx].surface, 'CANNOT', db_parcelles[p_idx].nom
            cultures_assignments[(c_idx, p_idx)] = solver.IntConst(0, 'c_%i_p_%i' % (c_idx, p_idx))
        print forced_surface, c_max_surfaces[c_idx]
        if forced_surface>c_max_surfaces[c_idx]:
            print db_cultures[c_idx].nom, db_cultures[c_idx].surface, forced_surface, "MUST CANCEL ONE OR MANY"
            culture_solver = pywrapcp.Solver("SUB")
            culture_surfaces = []
            culture_forced = []
            for p_idx in forced_parcelles:
                culture_surfaces.append(p_surfaces[p_idx])
                culture_forced.append(culture_solver.IntVar(0,1, 'c_%i_f_%i' % (c_idx, p_idx)))
            culture_solver.Add(culture_solver.ScalProd(culture_forced, culture_surfaces)==culture_solver.IntVar(c_min_surfaces[c_idx], c_max_surfaces[c_idx], 'c_surface_%i' % c_idx))
            f_solution = culture_solver.Assignment()
            f_solution.Add(culture_forced)
            f_phase = culture_solver.Phase(culture_forced, culture_solver.INT_VAR_SIMPLE, culture_solver.ASSIGN_MAX_VALUE)
            culture_solver.NewSearch(f_phase)
            while culture_solver.NextSolution():
                forced_parcelles = [forced_parcelles[index] for index in range(0, len(forced_parcelles)) if culture_forced[index].Value()==1]
                print "FOUND CANCEL", forced_parcelles
                break
            culture_solver.EndSearch()
        for p_idx in forced_parcelles:
            print db_cultures[c_idx].nom, db_cultures[c_idx].surface, 'MUST', db_parcelles[p_idx].nom,db_parcelles[p_idx].surface 
            for sub_c_idx in c_range:
                cultures_assignments[(c_idx, p_idx)] = solver.IntConst(1 if sub_c_idx==c_idx else 0, 'c_%i_p_%i' % (c_idx, p_idx))
        solver.Add(solver.ScalProd([cultures_assignments[(c_idx, p_idx)] for p_idx in p_range], p_surfaces)==c_surface)
    # Rien ou une seule culture par parcelle
    for p_idx in p_range:
        solver.Add(solver.Sum([cultures_assignments[(c_idx, p_idx)] for c_idx in c_range])<=1)        
    # Convert to list
    for c_idx in c_range:
        for p_idx in p_range:
            cultures_assignments_as_list.append(cultures_assignments[(c_idx, p_idx)])
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
