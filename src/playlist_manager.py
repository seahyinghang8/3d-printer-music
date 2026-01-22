"""Playlist management for 3D printer music player."""

import random
from pathlib import Path
from typing import Any, Optional

import yaml


class PlaylistManager:
    """
    Manage MIDI playlist with YAML persistence.

    Handles:
    - Loading/saving playlist from/to YAML
    - Tracking played status
    - Shuffle order management
    - Getting next unplayed item
    """

    def __init__(self, playlist_path: str):
        """
        Initialize playlist manager.

        Args:
            playlist_path: Path to YAML playlist file
        """
        self.playlist_path = Path(playlist_path)
        self.playlist_data: dict[str, Any] = {}

    def load_playlist(self) -> dict[str, Any]:
        """
        Load playlist from YAML file.

        Always reads from disk to support live editing.

        Returns:
            Playlist dictionary with 'items' key

        Raises:
            FileNotFoundError: Playlist file not found
            yaml.YAMLError: Invalid YAML format
        """
        with open(self.playlist_path, 'r') as f:
            self.playlist_data = yaml.safe_load(f)

        # Ensure required keys exist
        if 'items' not in self.playlist_data:
            self.playlist_data['items'] = []

        return self.playlist_data

    def save_playlist(self) -> None:
        """
        Save current playlist data to YAML file.

        Persists changes like played status and shuffle order.
        """
        with open(self.playlist_path, 'w') as f:
            yaml.safe_dump(self.playlist_data, f, default_flow_style=False, sort_keys=False)

    def get_next_unplayed_item(self) -> Optional[tuple[int, dict[str, Any]]]:
        """
        Get the next unplayed item from the playlist.

        Returns:
            Tuple of (index, item_dict) for next unplayed item
            None if all items have been played
        """
        items = self.playlist_data.get('items', [])

        # Find first unplayed item in sequential order
        for idx, item in enumerate(items):
            if not item.get('played', False):
                return idx, item

        return None

    def mark_as_played(self, index: int) -> None:
        """
        Mark an item as played and save to YAML.

        Args:
            index: Index of item in the items list
        """
        items = self.playlist_data.get('items', [])
        if 0 <= index < len(items):
            items[index]['played'] = True
            self.save_playlist()

    def shuffle(self) -> None:
        """
        Shuffle the items array in-place and save to YAML.

        Randomly reorders all items in the playlist.
        """
        items = self.playlist_data.get('items', [])
        random.shuffle(items)
        self.playlist_data['items'] = items
        self.save_playlist()

    def reset_played_status(self) -> None:
        """
        Reset all items to unplayed status and save to YAML.

        Useful for replaying the entire playlist.
        """
        items = self.playlist_data.get('items', [])
        for item in items:
            item['played'] = False
        self.save_playlist()
