import { defineSport, type SportDefinition } from "@clubos/core";
import definition from "../sport.json";

// Goalkeeping comparison covers distribution only until a shot-stopping metric
// (post-shot xG) is available from the data connector.
export const soccer = defineSport(definition as unknown as SportDefinition);
