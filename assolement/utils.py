'''
Created on 3 fevr. 2016

@author: humble_jok
'''
from ortools.constraint_solver import pywrapcp
import itertools
from assolement.models import Parcel, Crop
import uuid

def make_int(fl_value):
    return int(fl_value * 1000.0)


def get_short_constraint(solver, label, crop, parcel, year, forbid_previous_not_recommanded, forbid_soil_not_recommanded):
    already_assigned = parcel.history.filter(year=year)
    if already_assigned.exists():
        already_assigned = already_assigned[0]
        if already_assigned.crop==crop:
            return solver.IntConst(1, label)
        else:
            return solver.IntConst(0, label)
    else:
        forbid = crop.soils_forbidden.filter(id=parcel.soil_kind.id)
        not_reco = crop.soils_not_reco.filter(id=parcel.soil_kind.id)
        if forbid.exists() or (forbid_soil_not_recommanded and not_reco.exists()):
            return solver.IntConst(0, label)
        previous = parcel.history.filter(annee=year-1)
        if previous.exists():
            previous = previous[0]
            forbid = crop.previous_forbidden.filter(id=previous.crop.id)
            not_reco = crop.previous_not_reco.filter(id=previous.crop.id)
            if forbid.exists() or (forbid_previous_not_recommanded and not_reco.exists()):
                return solver.IntConst(0, label)
        if crop.years_return>0:
            for back_index in range(1, crop.years_return + 1):
                previous = parcel.history.filter(year=year-back_index, crop__id=crop.id)
                if previous.exists():
                    return solver.IntConst(0, label)
        return solver.IntVar(0,1, label)

def get_crop_long_constraints(crop_information, db_parcels, c_min_surfaces, c_max_surfaces):
    crop_solver = pywrapcp.Solver(uuid.uuid4().hex)
    crop_surfaces = []
    crop_forced = []
    for p_idx in crop_information['db_parcels']:
        crop_surfaces.append(make_int(db_parcels[p_idx].surface))
        crop_forced.append(crop_solver.IntVar(0,1, 'c_%i_f_%i' % (crop_information['c_idx'], p_idx)))
    crop_solver.Add(crop_solver.ScalProd(crop_forced, crop_surfaces)==crop_solver.IntVar(0, c_max_surfaces[crop_information['c_idx']], 'c_surface_%i' % crop_information['c_idx']))
    f_solution = crop_solver.Assignment()
    f_solution.Add(crop_forced)
    f_phase = crop_solver.Phase(crop_forced, crop_solver.INT_VAR_SIMPLE, crop_solver.ASSIGN_MAX_VALUE)
    crop_solver.NewSearch(f_phase)
    all_solutions = []
    all_valid_solutions = []
    while crop_solver.NextSolution():
        forced_parcels = [crop_information['db_parcels'][index] for index in range(0, len(crop_information['db_parcels'])) if crop_forced[index].Value()==1]
        all_solutions.append(forced_parcels)
        surface = 0
        for p_idx in forced_parcels:
            surface += make_int(db_parcels[p_idx].surface)
        if surface>c_min_surfaces[crop_information['c_idx']]:
            all_valid_solutions.append(forced_parcels)
    crop_solver.EndSearch()
    return (all_valid_solutions, True) if len(all_valid_solutions)>0 else (all_solutions, False)

def get_long_constraints(db_parcels, crops, c_min_surfaces, c_max_surfaces, year):
    constraints = {}
    p_idx = 0
    long_crops = {}
    for parcel in db_parcels:
        previous = parcel.history.filter(year=year-1, crop__crop_duration__gt=1)
        if previous.exists():
            crop = previous[0].crop
            c_idx = crops.index(crop.id)
            count = 0
            for working_year in reversed(range(year-crop.crop_duration, year)):
                previous = parcel.history.filter(year=working_year, crop__id=crop.id)
                if previous.exists():
                    count += 1
                else:
                    break
            if count>0 and count<crop.crop_duration:
                if crop.id not in long_crops:
                    long_crops[crop.id] = {'db_parcels': [], 'surface': 0, 'crop': crop, 'c_idx': c_idx}
                long_crops[crop.id]['db_parcels'].append(p_idx)
                long_crops[crop.id]['surface'] += make_int(parcel.surface)
        p_idx += 1
    for crop_id in long_crops:
        if long_crops[crop_id]['surface']>c_max_surfaces[long_crops[crop.id]['c_idx']]:
            constraints[long_crops[crop.id]['c_idx']] = []
            all_alternatives = get_crop_long_constraints(long_crops[crop.id], db_parcels, c_min_surfaces, c_max_surfaces)
            for alternative in all_alternatives[0]:
                sub_constraints = {}
                for p_idx in range(0, len(db_parcels)):
                    if p_idx in alternative:
                        sub_constraints[(long_crops[crop.id]['c_idx'], p_idx)] = 1
                    elif all_alternatives[1]:
                        sub_constraints[(long_crops[crop.id]['c_idx'], p_idx)] = 0
                constraints[long_crops[crop.id]['c_idx']].append(sub_constraints)
        else:
            sub_constraints = {}
            for p_idx in long_crops[crop.id]['db_parcels']:
                sub_constraints[(long_crops[crop.id]['c_idx'], p_idx)] = 1
            constraints[long_crops[crop.id]['c_idx']] = [sub_constraints]
    return constraints

def assolement_computer(working_year, user):
    solutions = {}
    
    db_parcels = Parcel.objects.filter(user__id=user.id, surface__gt=0.0).order_by('name')
    db_crops = Crop.objects.filter(user__id=user.id,surface__gt=0.0).order_by('name')
    crops = [crop.id for crop in db_crops]
    parcels = [parcel.id for parcel in db_parcels]
    
    p_surfaces = [make_int(parcel.surface) for parcel in db_parcels]
    
    c_range = range(0, len(crops))
    p_range = range(0, len(parcels))
    
    c_min_surfaces = [make_int(crop.surface * (1.0 - (crop.threshold / 100.0))) for crop in db_crops]
    c_max_surfaces = [make_int(crop.surface * (1.0 + (crop.threshold / 100.0))) for crop in db_crops]
    
    long_constraints = get_long_constraints(db_parcels, crops, c_min_surfaces, c_max_surfaces, working_year)
    num_solutions = 0
    # solver_type: 2 = CHOOSE_FIRST_UNBOUND, 1 = INT_VAR_SIMPLE
    # solver_type: 3 = ASSIGN_MAX_VALUE, 5 = ASSIGN_CENTER_VALUE
    for force_mandatory in [True, False]:
        for previous_reco in [True, False]:
            for soil_reco in [True, False]:
                for constraints in itertools.product(*long_constraints.values()):    
                    solver = pywrapcp.Solver('Rotation ' + str(working_year) + ' for ' + str(user.username))
                    crops_assignments = {}
                    crops_assignments_as_list = []
                    objectives = []
                    # Assigning defaults
                    for c_idx in c_range:
                        for p_idx in p_range:
                            crops_assignments[(c_idx, p_idx)] = get_short_constraint(solver, 'c_%i_p_%i' % (c_idx, p_idx), db_crops[c_idx], db_parcels[p_idx], working_year, previous_reco, soil_reco)
                    for assigments in constraints:
                        for key in assigments:
                            crops_assignments[key] = solver.IntConst(assigments[key], 'c_%i_p_%i' % key)
                    # No crop or only one crop per parcel
                    for p_idx in p_range:
                        solver.Add(solver.Sum([crops_assignments[(c_idx, p_idx)] for c_idx in c_range])<=1)
                    # Assign constraints
                    for c_idx in c_range:
                        c_surface = solver.IntVar(c_min_surfaces[c_idx] if db_crops[c_idx].mandatory and force_mandatory else 0, c_max_surfaces[c_idx], 'c_surface_%i' % c_idx)
                        objectives.append(solver.Maximize(c_surface, 1000))
                        solver.Add(solver.ScalProd([crops_assignments[(c_idx, p_idx)] for p_idx in p_range], p_surfaces)==c_surface)
                    # Convert to list
                    for c_idx in c_range:
                        for p_idx in p_range:
                            crops_assignments_as_list.append(crops_assignments[(c_idx, p_idx)])
                            
                    
                            
                    solution = solver.Assignment()
                    solution.Add(crops_assignments_as_list)
                    
                    phase = solver.Phase(crops_assignments_as_list, solver.CHOOSE_FIRST_UNBOUND, solver.ASSIGN_MAX_VALUE)
                    solver.NewSearch(phase, objectives)
            
                    while solver.NextSolution():
                        solutions[num_solutions] = {}
                        print "SOLUTION NO:", num_solutions
                        for c_idx in c_range:
                            solutions[num_solutions][crops[c_idx]] = {'allocation': [], 'allocated_surface': 0.0, 'match': False}
                            for p_idx in p_range:
                                solutions[num_solutions][crops[c_idx]]['allocated_surface'] += db_crops[p_idx].surface * crops_assignments[(c_idx, p_idx)].Value()
                                if crops_assignments[(c_idx, p_idx)].Value()==1:
                                    solutions[num_solutions][crops[c_idx]]['allocation'].append(parcels[p_idx])
                            crop = db_crops[c_idx]
                            solutions[num_solutions][crops[c_idx]]['match'] = solutions[num_solutions][crops[c_idx]]['allocated_surface']>=(crop.surface * (1.0 - (crop.threshold / 100.0))) and solutions[num_solutions][crops[c_idx]]['allocated_surface']<=(crop.surface * (1.0 + (crop.threshold / 100.0)))
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