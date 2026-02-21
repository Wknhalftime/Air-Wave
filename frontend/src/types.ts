export interface QueueItem {
    signature: string;
    raw_artist: string;
    raw_title: string;
    count: number;
    suggested_work_id: number | null;  // Phase 4: Work-level suggestion
    suggested_work?: {
        id: number;
        title: string;
        artist?: {
            name: string;
        }
    }
}

export interface AuditEntry {
    id: number;
    created_at: string;
    action_type: string;
    raw_artist: string;
    raw_title: string;
    recording_title: string | null;
    recording_artist: string | null;
    log_count: number;
    can_undo: boolean;
    undone_at: string | null;
}

export interface ArtistQueueItem {
    raw_name: string;
    item_count: number;
    is_verified: boolean;
    suggested_artist?: {
        id: number;
        name: string;
    };
}
