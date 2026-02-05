export interface QueueItem {
    signature: string;
    raw_artist: string;
    raw_title: string;
    count: number;
    suggested_recording_id: number | null;
    suggested_recording?: {
        id: number;
        title: string;
        work?: {
            artist?: {
                name: string;
            }
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
