# Evaluation (k=6, threshold=0.6885)

| metric | value |
|---|---|
| doc_hit_rate@6_en | 1.0 |
| section_hit_rate@6_en | 1.0 |
| false_refusal_rate_en | 0.0 |
| refusal_accuracy_en | 1.0 |
| doc_hit_rate@6_es | 1.0 |
| section_hit_rate@6_es | 1.0 |
| false_refusal_rate_es | 0.0 |
| refusal_accuracy_es | 1.0 |
| keyword_coverage | n/a |

| id | lang | type | grounded | max score | doc hit | section hit | retrieved |
|---|---|---|---|---|---|---|---|
| e2a_fatal_timeline | en | in_domain | yes | 0.878 | yes | yes | ich_e2a §1, ich_e2a §2, ich_e2a §1 |
| e2a_fatal_timeline | es | in_domain | yes | 0.821 | yes | yes | ich_e2a §1, ich_e2a §1, ich_e2a §2 |
| helsinki_incapable_consent | en | in_domain | yes | 0.834 | yes | yes | wma_helsinki_2024 §28, wma_helsinki_2024 §28, wma_helsinki_2024 §30 |
| helsinki_incapable_consent | es | in_domain | yes | 0.800 | yes | yes | wma_helsinki_2024 §28, wma_helsinki_2024 §28, wma_helsinki_2024 §30 |
| ood_glp1_weight_loss | en | ood | no | 0.627 | - | - | ich_e6_r3 §B.7.3, wma_helsinki_2024 §33, ich_e6_r3 §B.7.2 |
| ood_glp1_weight_loss | es | ood | no | 0.557 | - | - | ich_e6_r3 §B.7.3, ich_e6_r3 §II, ich_e6_r3 §B.7.1 |
