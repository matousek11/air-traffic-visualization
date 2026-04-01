/**
 * MTCD event shape returned by the database-service API.
 */
export type ApiMTCDEventStructure = {
  id: number;
  flight_id_1: string;
  flight_id_2: string;
  detected_at: string;
  horizontal_distance: number | null;
  vertical_distance: number | null;
  remaining_time: number | null;
  middle_point_lat: number | null;
  middle_point_lon: number | null;
  flight_1_conflict_entry_lat: number | null;
  flight_1_conflict_entry_lon: number | null;
  flight_1_conflict_entry_flight_level: number | null;
  flight_1_conflict_exit_lat: number | null;
  flight_1_conflict_exit_lon: number | null;
  flight_1_conflict_exit_flight_level: number | null;
  flight_2_conflict_entry_lat: number | null;
  flight_2_conflict_entry_lon: number | null;
  flight_2_conflict_entry_flight_level: number | null;
  flight_2_conflict_exit_lat: number | null;
  flight_2_conflict_exit_lon: number | null;
  flight_2_conflict_exit_flight_level: number | null;
  active: boolean;
  last_checked: string | null;
};
