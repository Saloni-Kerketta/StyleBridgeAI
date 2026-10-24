import numpy as np
from app.models import neighbour_scores
from app.evaluation import ndcg_at_k, recall_at_k, hit_rate_at_k
import math


def test_recommends_what_similar_shoppers_bought_not_what_dissimilar_bought():
    # users: 0 = me, 1 = similar to me, 2 = not similar. items: 0 shared, 1 bought by similar, 2 bought by dissimilar
    sim_row = np.array([0.0, 0.9, 0.0])
    signal = np.array([[1, 0, 0],
                       [1, 1, 0],
                       [0, 0, 1]], float)
    scores, support, idx, sims = neighbour_scores(sim_row, signal, k=5)
    assert list(idx) == [1] and scores[1] > 0 and scores[2] == 0
    assert list(support) == [1, 1, 0]


def test_only_shoppers_who_bought_in_the_domain_contribute():
    sim_row = np.array([0.0, 0.9, 0.5])
    signal_dom = np.array([[0, 0], [0, 0], [0, 3]], float)       # shopper 1 is closest but bought nothing here
    scores, support, idx, sims = neighbour_scores(sim_row, signal_dom, k=1)
    assert list(idx) == [2] and scores[1] == 1.5


def test_no_neighbours_gives_zero_scores():
    scores, support, idx, sims = neighbour_scores(np.zeros(3), np.ones((3, 2)), k=3)
    assert len(idx) == 0 and not scores.any()


def test_k_limits_neighbours():
    sim_row = np.array([0.0, 0.9, 0.8, 0.7])
    _, _, idx, _ = neighbour_scores(sim_row, np.ones((4, 2)), k=2)
    assert list(idx) == [1, 2]


def test_ranking_metrics():
    assert ndcg_at_k([1, 2, 3], {1, 2}, 3) == 1.0 and ndcg_at_k([7, 8], {1}, 2) == 0.0
    assert math.isclose(ndcg_at_k([9, 1, 8], {1}, 3), 1 / math.log2(3))
    assert recall_at_k([1, 2, 3], {1, 5}, 3) == 0.5 and hit_rate_at_k([5], {5}, 1) == 1.0
