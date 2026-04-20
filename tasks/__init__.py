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
from .level_splitter_task import LevelSplitterTask, SplitterConfig, SplitterResult
from .unknown_reviewer_task import UnknownReviewerTask, ReviewerConfig, ReviewStats
from .frame_analyzer_task import FrameAnalyzerTask, AnalyzerConfig, AnalysisResult
from .dataset_annotator_task import DatasetAnnotatorTask, AnnotatorConfig, ClassInfo
from .dataset_augmentation_task import DatasetAugmentationTask, AugmentationResult
from .batch_predict_task import BatchPredictTask, PredictConfig, PredictResult



__all__ = [
    'BaseTask', 'TaskStatus', 'TaskPriority', 
    'ScraperTask', 'DownloadTask', 'ViewerTask', 'MetricsTask',
    'FrameExtractionTask', 'FrameCleaningTask', 'AdvancedBlurTask', 
    'AutoCropTask', 'CropComparisonTask', 'MarioMenuTask', 
    'SegmentTransitionTask', 'MarioLevelSegmentTask',
    'YOLOTrainingTask', 'TrainingConfig', 'TrainingResult',
    'LevelSplitterTask', 'SplitterConfig', 'SplitterResult',
    'UnknownReviewerTask', 'ReviewerConfig', 'ReviewStats',
    'FrameAnalyzerTask', 'AnalyzerConfig', 'AnalysisResult',
    'DatasetAnnotatorTask', 'AnnotatorConfig', 'ClassInfo',
    'DatasetAugmentationTask', 'AugmentationResult', 
    'BatchPredictTask', 'PredictConfig', 'PredictResult',

    
]