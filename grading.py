from models import QuestionType
import json
from models import QuestionType, MatchPair

def auto_grade_test(questions, answers_by_qid):
    score = 0.0
    max_score = 0.0
    manual_required = False

    for q in questions:
        max_score += q.points
        ans = answers_by_qid.get(q.id)
        if q.qtype == QuestionType.TEXT:
            manual_required = True
            continue
        if q.qtype == QuestionType.SINGLE:
            # ans = option_id (int)
            correct = [o.id for o in q.options if o.is_correct]
            if ans and int(ans) in correct:
                score += q.points
        elif q.qtype == QuestionType.MULTI:
            # ans = set(option_ids)
            correct = {o.id for o in q.options if o.is_correct}
            if ans is not None and set(map(int, ans)) == correct:
                score += q.points
        elif q.qtype == QuestionType.ORDER:
            # ans = list(option_ids) — точное совпадение
            correct_order = [o.id for o in sorted(q.options, key=lambda x: x.order_idx)]
            if ans and list(map(int, ans)) == correct_order:
                score += q.points
        else:
            # прочие типы — пока как SINGLE
            correct = [o.id for o in q.options if o.is_correct]
            if ans and int(ans) in correct:
                score += q.points

    return score, max_score, manual_required

def _apply_grading_policy(base_score, attempt_index: int, policy_json: str|None):
    """Масштабирование балла в зависимости от попытки, + ручная проверка после N-й попытки."""
    if not policy_json:
        return base_score, False
    try:
        policy = json.loads(policy_json)
    except Exception:
        return base_score, False

    manual_after = policy.get("manual_after_attempt")
    manual_required = bool(manual_after and attempt_index >= int(manual_after))

    scale = 1.0
    per = policy.get("per_attempt_scale") or {}
    if str(attempt_index) in per:
        try:
            scale = float(per[str(attempt_index)])
        except Exception:
            scale = 1.0

    return base_score * scale, manual_required

def auto_grade_test(test, questions, answers_by_qid, attempt_index: int):
    score = 0.0
    max_score = 0.0
    manual_required_any = False

    for q in questions:
        max_score += q.points
        ans = answers_by_qid.get(q.id)

        if q.qtype == QuestionType.TEXT:
            manual_required_any = True
            continue

        if q.qtype == QuestionType.SINGLE:
            correct = [o.id for o in q.options if o.is_correct]
            if ans and int(ans) in correct:
                score += q.points

        elif q.qtype == QuestionType.MULTI:
            correct = {o.id for o in q.options if o.is_correct}
            if ans is not None and set(map(int, ans)) == correct:
                score += q.points

        elif q.qtype == QuestionType.ORDER:
            correct_order = [o.id for o in sorted(q.options, key=lambda x: x.order_idx)]
            if ans:
                arr = list(map(int, ans))
                if arr == correct_order:
                    score += q.points

        elif q.qtype == QuestionType.MATCH:
            # ans = list of "left_id:right_id" or JSON
            # MVP: сравниваем кол-во правильных соответствий
            correct_pairs = {(mp.left_text.strip(), mp.right_text.strip()) for mp in MatchPair.query.filter_by(question_id=q.id).all()}
            user_pairs = set()
            if isinstance(ans, list):
                for p in ans:
                    if ":" in p:
                        l, r = p.split(":", 1)
                        user_pairs.add((l.strip(), r.strip()))
            # Простая проверка: точное совпадение множества
            if user_pairs and user_pairs == correct_pairs:
                score += q.points

        else:
            # fallback как SINGLE
            correct = [o.id for o in q.options if o.is_correct]
            if ans and int(ans) in correct:
                score += q.points

    # применить политику теста (масштабирование, принудительная ручная проверка)
    scaled, policy_manual = _apply_grading_policy(score, attempt_index, test.grading_policy_json)
    manual_required_any = manual_required_any or policy_manual

    return scaled, max_score, manual_required_any