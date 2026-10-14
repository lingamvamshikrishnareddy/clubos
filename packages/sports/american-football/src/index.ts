import { defineSport, type SportDefinition } from "@clubos/core";
import definition from "../sport.json";

export const americanFootball = defineSport(definition as unknown as SportDefinition);
