"""
UI Package - Interface utilisateur de l'application
"""

from .main_window import MainWindow
from .viewer_window import ViewerWindow
from .metrics_window import MetricsWindow
from .frame_viewer_window import FrameViewerWindow
from .frame_cleaning_widget import FrameCleaningWidget
from .advanced_blur_widget import AdvancedBlurWidget
from .auto_crop_widget import AutoCropWidget
from .crop_comparison_widget import CropComparisonWidget
from .mario_menu_widget import MarioMenuWidget
from .segment_transition_widget import SegmentTransitionWidget
from .mario_level_segment_widget import MarioLevelSegmentWidget
from .yolo_training_widget import YOLOTrainingWidget
from .level_splitter_widget import LevelSplitterWidget
from .unknown_reviewer_widget import UnknownReviewerWidget
from .frame_analyzer_widget import FrameAnalyzerWidget
from .dataset_annotator_widget import DatasetAnnotatorWidget
from .interpolation_dialog import InterpolationDialog
from .dataset_augmentation_widget import DatasetAugmentationWidget



__all__ = [
    
    'MainWindow', 'ViewerWindow', 'MetricsWindow', 
    'FrameViewerWindow', 'FrameCleaningWidget', 'AdvancedBlurWidget', 
    'AutoCropWidget', 'CropComparisonWidget', 'MarioMenuWidget', 'SegmentTransitionWidget',
    'MarioLevelSegmentWidget','YOLOTrainingWidget', 'LevelSplitterWidget', 'UnknownReviewerWidget',
    'FrameAnalyzerWidget', 'DatasetAnnotatorWidget', 'InterpolationDialog', 'DatasetAugmentationWidget'

]