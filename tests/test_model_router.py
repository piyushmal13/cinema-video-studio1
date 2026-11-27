import unittest
from scripts.model_router import recommend, REGISTRY

class ModelAdmissionTests(unittest.TestCase):
    def test_no_nvidia_gpu_never_schedules_local_diffusion(self):
        result=recommend([])
        self.assertFalse(result["local_diffusion_allowed"])
        self.assertEqual(result["profile"],"cpu-editorial")
        self.assertEqual(result["eligible_models"],[])

    def test_four_gb_gpu_is_not_approved_for_diffusion(self):
        result=recommend([{"total_gb":4,"free_gb":3.5}])
        self.assertFalse(result["local_diffusion_allowed"])

    def test_eight_gb_gpu_requires_safety_margin_and_does_not_claim_all_models(self):
        result=recommend([{"total_gb":8,"free_gb":7.5}])
        self.assertFalse(result["local_diffusion_allowed"])

    def test_large_gpu_admits_only_models_below_threshold(self):
        result=recommend([{"total_gb":48,"free_gb":44}])
        self.assertIn("ltx-2.5-22b",result["eligible_models"])
        self.assertNotIn("wan2.2-a14b",result["eligible_models"])

    def test_model_registry_distinguishes_code_and_weight_licence(self):
        self.assertIn("Community License",REGISTRY["ltx-2.5-22b"]["weight_license"])
        self.assertEqual(REGISTRY["wan2.2-a14b"]["min_vram_gb"],80.0)

if __name__=="__main__":unittest.main()
