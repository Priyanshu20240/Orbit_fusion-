import ee
from services.gee_fusion_service import GEEFusionService
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_ndvi_fusion():
    try:
        service = GEEFusionService()
        if not service.initialized:
            logger.error("GEE not initialized")
            return

        # Define a small test area (New Delhi)
        bounds = (77.10, 28.50, 77.30, 28.70)
        start_date = "2023-01-01"
        end_date = "2023-01-31"

        logger.info("Testing NDVI Fusion...")
        result = service.create_harmonized_fusion(
            bounds=bounds,
            start_date=start_date,
            end_date=end_date,
            visualization='ndvi',
            platforms=['sentinel', 'landsat'] # Test BOTH to trigger fusion logic
        )

        if result.get('success'):
            logger.info("NDVI Fusion successful!")
            logger.info(f"Image URL: {result.get('imageUrl')}")
        else:
            logger.error(f"NDVI Fusion failed: {result.get('error')}")

        logger.info("Testing SWIR Fusion...")
        result_swir = service.create_harmonized_fusion(
            bounds=bounds,
            start_date=start_date,
            end_date=end_date,
            visualization='false_color_swir',
            platforms=['sentinel']
        )

        if result_swir.get('success'):
            logger.info("SWIR Fusion successful!")
        else:
            logger.error(f"SWIR Fusion failed: {result_swir.get('error')}")

    except Exception as e:
        logger.exception(f"Exception during test: {e}")

if __name__ == "__main__":
    test_ndvi_fusion()
