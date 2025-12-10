"""
Tasks Package - Contient toutes les tâches du pipeline
"""

from .base_task import BaseTask, TaskStatus, TaskPriority
from .scraper_task import ScraperTask
from .download_task import DownloadTask
from .viewer_task import ViewerTask
from .metrics_task import MetricsTask
from .frame_extraction_task import FrameExtractionTask
from .frame_cleaning_task import FrameCleaningTask
from .advanced_blur_task import AdvancedBlurTask
from .auto_crop_task import AutoCropTask
from .crop_comparison_task import CropComparisonTask
from .mario_menu_task import MarioMenuTask
from .segment_transition_task import SegmentTransitionTask
from .mario_level_segment_task import MarioLevelSegmentTask
from .yolo_training_task import YOLOTrainingTask, TrainingConfig, TrainingResult


__all__ = [
    'BaseTask', 'TaskStatus', 'TaskPriority', 
    'ScraperTask', 'DownloadTask', 'ViewerTask', 'MetricsTask',
    'FrameExtractionTask', 'FrameCleaningTask', 'AdvancedBlurTask', 
    'AutoCropTask', 'CropComparisonTask', 'MarioMenuTask', 'SegmentTransitionTask', 'MarioLevelSegmentTask',
    'YOLOTrainingTask', 'TrainingConfig', 'TrainingResult'
]