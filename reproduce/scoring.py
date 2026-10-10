"""Historical semantic rule. Grades are saved judgements, not a new review."""
def citation_needed(case: dict) -> bool:
    return case['answerability'] in ('answerable', 'limited', 'partial')

def validate_grade(case: dict, row: dict, outcome: dict, grade: dict) -> dict:
    record = outcome['record']
    if grade.get('item_id') != row['item_id'] or grade.get('outcome_sha256') != outcome['sha256'] or grade.get('reviewer_type') not in ('ai', 'human') or not grade.get('reviewer') or not grade.get('rationale'):
        raise ValueError('Semantic judgement must identify the actual output and real reviewer')
    checked = grade.get('requirements', [])
    if len(checked) != len(case['answer_requirements']) or {r['requirement_id'] for r in checked} != {r['requirement_id'] for r in case['answer_requirements']}:
        raise ValueError('All required subquestions must be judged; no dropping a missing second question')
    for requirement in case['answer_requirements']:
        decision = next(d for d in checked if d['requirement_id'] == requirement['requirement_id'])
        if type(decision.get('satisfied')) is not bool or not decision.get('rationale'):
            raise ValueError('Requirement needs an explicit semantic judgement')
        allowed = {alt['variant_id'] for alt in requirement['alternatives']}
        if decision['satisfied'] and decision.get('accepted_variant_id') not in allowed:
            raise ValueError('Satisfied requirements must cover a reviewed variant semantically')
    for name in ('action_correct', 'no_unsupported_claims', 'user_constraints_correct', 'query_faithful', 'intent_behavior_correct'):
        if type(grade.get(name)) is not bool:
            raise ValueError('Required semantic field missing: ' + name)
    if grade.get('observed_action') not in ('answer', 'partial', 'refuse', 'clarify'):
        raise ValueError('Actual answer action must be semantically identified for every arm')
    if grade.get('reviewer_relationship') not in ('same_developer_ai', 'separate_ai', 'human'):
        raise ValueError('Reviewer independence must be explicitly disclosed')
    if case['missing_information'] and type(grade.get('scope_limitations_correct')) is not bool:
        raise ValueError('Partial/unreported/limited scope must be explicitly evaluated')
    if case['dialogue_id'] and row['turn_index'] > 1 and type(grade.get('memory_consistent')) is not bool:
        raise ValueError('Actual preceding dialogue and language corrections must be reviewed')
    cited = set(record.get('citation_validity', {}).get('cited_ids', []))
    bindings = grade.get('citation_bindings', [])
    if {c['citation_id'] for c in bindings} != cited or any(type(c.get('supported')) is not bool or not c.get('rationale') for c in bindings):
        raise ValueError('Each actual citation needs a source-support judgement')
    final_id = record.get('final_request_id')
    final_request = next((r for r in record['requests'] if r['request_id'] == final_id), None)
    visible = {c['chunk_id'] for t in (final_request or {}).get('tool_context', []) for c in t['visible_chunks']}
    citation_ok = all(c['supported'] and c['citation_id'] in visible for c in bindings)
    if cited and not final_request:
        citation_ok = False
    if citation_needed(case) and not cited:
        citation_ok = False
    task = record['status'] == 'completed' and all(d['satisfied'] for d in checked) and grade['action_correct'] and grade['no_unsupported_claims'] and grade['user_constraints_correct'] and citation_ok and grade.get('scope_limitations_correct', True) is not False and grade.get('memory_consistent', True) is not False
    return {'task_correct': task, 'citation_correct': citation_ok, 'false_refusal': grade['observed_action'] == 'refuse',
            **{k: grade.get(k) for k in ('action_correct', 'query_faithful', 'intent_behavior_correct', 'memory_consistent')}}
