import { fetcher } from "../lib/api";

export interface Bridge {
    id: number;
    log_signature: string;
    reference_artist: string;
    reference_title: string;
    recording_id: number;
    is_revoked: boolean;
    updated_at: string;
    recording: {
        title: string;
        work: {
            artist: {
                name: string;
            };
        };
    };
    created_at?: string;
}

export interface ListBridgesParams {
    page?: number;
    page_size?: number;
    search?: string;
    include_revoked?: boolean;
}

export const bridgesApi = {
    list: async (params: ListBridgesParams = {}) => {
        const searchParams = new URLSearchParams();
        if (params.page) searchParams.append("page", params.page.toString());
        if (params.page_size) searchParams.append("page_size", params.page_size.toString());
        if (params.search) searchParams.append("search", params.search);
        if (params.include_revoked) searchParams.append("include_revoked", "true");

        // fetcher returns the JSON body directly
        return fetcher<Bridge[]>(`/identity/bridges/?${searchParams.toString()}`);
    },

    updateStatus: async (id: number, is_revoked: boolean) => {
        return fetcher<Bridge>(`/identity/bridges/${id}?is_revoked=${is_revoked}`, {
            method: 'PATCH',
        });
    },
};
