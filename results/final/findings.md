# Measured benchmark findings

These observations are generated from the saved runs. Positive improvement means a shorter route than Nearest Neighbor.

## 5 customers + one depot

GA mean distance: 255.463365; Random Search mean: 255.463365; Nearest Neighbor: 255.497576.
GA was worse than Nearest Neighbor in 0/10 runs and worse than its paired Random Search run in 0/10 runs.
GA mean improvement over Nearest Neighbor: 0.013%. Mean GA time: 0.554662 s; mean Random Search time: 0.049896 s.
Exact optimum: 255.463365; GA mean optimality gap: 0.000%.

## 10 customers + one depot

GA mean distance: 368.833300; Random Search mean: 404.099751; Nearest Neighbor: 422.284877.
GA was worse than Nearest Neighbor in 0/10 runs and worse than its paired Random Search run in 0/10 runs.
GA mean improvement over Nearest Neighbor: 12.658%. Mean GA time: 0.694632 s; mean Random Search time: 0.063480 s.
Exact optimum: 368.392706; GA mean optimality gap: 0.120%.

## 20 customers + one depot

GA mean distance: 381.024630; Random Search mean: 659.655220; Nearest Neighbor: 380.682773.
GA was worse than Nearest Neighbor in 3/10 runs and worse than its paired Random Search run in 0/10 runs.
GA mean improvement over Nearest Neighbor: -0.090%. Mean GA time: 1.011534 s; mean Random Search time: 0.088152 s.
Exact optimum was not computed because the dataset exceeds the 12-customer limit.

The measured losses are consistent with finite-budget stochastic search. The pure GA starts from random permutations; tournament selection and finite population diversity can converge to a local region. Nearest Neighbor exploits local geometry immediately. This experiment does not establish a single causal mechanism or universal algorithm ranking.

## 30 customers + one depot

GA mean distance: 493.378999; Random Search mean: 1131.349229; Nearest Neighbor: 609.247341.
GA was worse than Nearest Neighbor in 0/10 runs and worse than its paired Random Search run in 0/10 runs.
GA mean improvement over Nearest Neighbor: 19.018%. Mean GA time: 0.863258 s; mean Random Search time: 0.074160 s.
Exact optimum was not computed because the dataset exceeds the 12-customer limit.

## Interpretation limits

There is one generated geometry per problem size. Repetitions measure algorithm RNG variability on that geometry, not variability across all delivery networks. Matching complete-tour evaluations does not match wall-clock time: crossover, selection, and Python overhead differ. Timings are machine-specific. Distances are Euclidean coordinate units and exclude roads, capacity, time windows, traffic, and multiple vehicles.
