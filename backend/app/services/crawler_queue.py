"""
Crawler Queue Service

Manages the queue of games to be crawled, with priority-based processing.
"""
import logging
from datetime import datetime
from typing import List, Dict, Optional
from app.db.firebase import get_db

logger = logging.getLogger(__name__)


class CrawlerQueue:
    """Service for managing the crawler queue"""

    COLLECTION = "crawler_queue"
    MAX_ATTEMPTS = 3

    def __init__(self):
        self.db = get_db()

    def enqueue(
        self,
        universe_ids: List[int],
        source: str,
        priority: int = 5
    ) -> Dict[str, int]:
        """
        Add universe IDs to the crawler queue.

        Args:
            universe_ids: List of Roblox universe IDs
            source: Source of the crawl (e.g., 'top_earning', 'keyword_search', 'user_import')
            priority: Priority level 1-10 (higher = processed first)

        Returns:
            Dict with 'enqueued' and 'updated' counts
        """
        enqueued = 0
        updated = 0

        for universe_id in universe_ids:
            doc_ref = self.db.collection(self.COLLECTION).document(str(universe_id))
            doc = doc_ref.get()

            if doc.exists:
                # Update existing entry: bump priority and update timestamp
                data = doc.to_dict()
                new_priority = max(data.get('priority', 0), priority)
                doc_ref.update({
                    'priority': new_priority,
                    'added_at': datetime.now(),
                    'source': source,  # Update to latest source
                })
                updated += 1
                logger.info(f"Updated queue entry for {universe_id}, priority: {new_priority}")
            else:
                # Create new entry
                doc_ref.set({
                    'universeId': universe_id,
                    'added_at': datetime.now(),
                    'priority': priority,
                    'source': source,
                    'attempts': 0,
                    'status': 'pending',
                    'error': None,
                })
                enqueued += 1
                logger.info(f"Enqueued {universe_id} from {source}, priority: {priority}")

        return {'enqueued': enqueued, 'updated': updated}

    def get_next_batch(self, limit: int = 50) -> List[Dict]:
        """
        Get the next batch of games to crawl, ordered by priority (highest first).

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of queue entries
        """
        query = (
            self.db.collection(self.COLLECTION)
            .where('status', '==', 'pending')
            .where('attempts', '<', self.MAX_ATTEMPTS)
            .order_by('priority', direction='DESCENDING')
            .order_by('added_at')
            .limit(limit)
        )

        entries = []
        for doc in query.stream():
            data = doc.to_dict()
            data['id'] = doc.id
            entries.append(data)

        logger.info(f"Retrieved {len(entries)} entries from queue")
        return entries

    def mark_processing(self, universe_id: int):
        """Mark a queue entry as being processed"""
        doc_ref = self.db.collection(self.COLLECTION).document(str(universe_id))
        doc_ref.update({
            'status': 'processing',
            'processing_started': datetime.now(),
        })

    def mark_done(self, universe_id: int):
        """Mark a queue entry as completed and remove it"""
        doc_ref = self.db.collection(self.COLLECTION).document(str(universe_id))
        doc_ref.delete()
        logger.info(f"Removed {universe_id} from queue (completed)")

    def mark_error(self, universe_id: int, error_msg: str):
        """Mark a queue entry as failed, increment attempts"""
        doc_ref = self.db.collection(self.COLLECTION).document(str(universe_id))
        doc = doc_ref.get()

        if not doc.exists:
            return

        data = doc.to_dict()
        attempts = data.get('attempts', 0) + 1

        if attempts >= self.MAX_ATTEMPTS:
            # Max attempts reached, mark as error
            doc_ref.update({
                'status': 'error',
                'attempts': attempts,
                'error': error_msg,
                'error_at': datetime.now(),
            })
            logger.error(f"Queue entry {universe_id} marked as error after {attempts} attempts: {error_msg}")
        else:
            # Retry later
            doc_ref.update({
                'status': 'pending',
                'attempts': attempts,
                'error': error_msg,
                'last_attempt': datetime.now(),
            })
            logger.warning(f"Queue entry {universe_id} failed (attempt {attempts}): {error_msg}")

    def get_stats(self) -> Dict:
        """Get crawler queue statistics"""
        pending = self.db.collection(self.COLLECTION).where('status', '==', 'pending').stream()
        processing = self.db.collection(self.COLLECTION).where('status', '==', 'processing').stream()
        errors = self.db.collection(self.COLLECTION).where('status', '==', 'error').stream()

        return {
            'queue_length': len(list(pending)),
            'processing': len(list(processing)),
            'errors': len(list(errors)),
        }

    def clear_errors(self):
        """Remove all error entries from the queue"""
        errors = self.db.collection(self.COLLECTION).where('status', '==', 'error').stream()
        count = 0
        for doc in errors:
            doc.reference.delete()
            count += 1

        logger.info(f"Cleared {count} error entries from queue")
        return count

    def reset_stuck_processing(self, timeout_minutes: int = 30):
        """
        Reset entries that have been 'processing' for too long back to 'pending'.

        Args:
            timeout_minutes: Time in minutes after which to consider an entry stuck
        """
        from datetime import timedelta

        cutoff = datetime.now() - timedelta(minutes=timeout_minutes)
        processing = self.db.collection(self.COLLECTION).where('status', '==', 'processing').stream()

        reset_count = 0
        for doc in processing:
            data = doc.to_dict()
            processing_started = data.get('processing_started')

            if processing_started and processing_started < cutoff:
                doc.reference.update({
                    'status': 'pending',
                    'processing_started': None,
                })
                reset_count += 1
                logger.warning(f"Reset stuck processing entry: {doc.id}")

        logger.info(f"Reset {reset_count} stuck processing entries")
        return reset_count
