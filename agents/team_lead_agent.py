import json
import logging
import os
from datetime import datetime
from utils import get_llm_agent
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field 

# ANSI color codes for logging hallucinations and errors
RED = "\033[91m"
RESET = "\033[0m"

class TeamLeadDecision(BaseModel):
    target_position: int = Field(description="The integer index(0-3) of the enemy to attack.")
    guessed_identity: str = Field(description="The guessed name of the hero at that position.")
    reasoning: str = Field(description="Brief strategy explaining why this target/guess was chosen.")
    
# set up parser
parser = JsonOutputParser(pydantic_object=TeamLeadDecision)    

class TeamLeadAgent:
    def __init__(self, team_name, model_name):
        self.llm = get_llm_agent(model_name, temperature=0.2)
        self.team_name = team_name
        self.known_enemies = {} 
        
        # Setup Internal Logging
        self.logger = self._setup_internal_logger()

        self.system_prompt = """
        You are the Team Lead Agent for a two-team battle game.
        
        GAME CONTEXT:
        - There are 4 positions on the enemy team: [0, 1, 2, 3].
        - You must choose a position to attack.
        - You must also GUESS the identity of the hero at that position (e.g., Argonian, Nord, Khajit, Nord, etc.).
        - If you guess correctly, you deal massive damage.
        
        CURRENT KNOWLEDGE (Enemies Revealed So Far):
        {known_enemies}
        
        YOUR MANAGER'S ORDER:
        Selected Hero: {acting_hero_name}
        Skill to Use: {acting_hero_skill}
        
        INSTRUCTIONS: 
        1. Choose a target position (0-3).
            - CRITICAL: Do NOT target a position if 'status' is 'dead'.
            - If you already know an enemy is at position 2 (as an example), targeting them is a safe hit.
            - If you don't know, pick a position and try to guess their identity.
        2. Do NOT guess a hero name that is already revealed at another position.
        3. Output MUST be valid JSON
        
        {format_instructions}
        """

        self.team_lead_prompt = PromptTemplate(
            template=self.system_prompt,
            input_variables=["known_enemies", "acting_hero_name", "acting_hero_skill"],
            partial_variables={"format_instructions": parser.get_format_instructions()}
        )

        self.chain = self.team_lead_prompt | self.llm | parser

    def _setup_internal_logger(self):
        """Configures logger to save in logs/ directory"""
        if not os.path.exists('logs'):
            os.makedirs('logs')
        
        # Unique logger name per team lead
        logger = logging.getLogger(f"Lead_{self.team_name.replace(' ', '_')}")
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            log_file = f"logs/battle_{datetime.now().strftime('%Y-%m-%d')}.log"
            file_handler = logging.FileHandler(log_file)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        return logger
    
    def get_turn_decision(self, manager_response):
        if manager_response.get("status") == "DEFEAT":
            self.logger.info("Manager signaled DEFEAT. Executing surrender.")
            return {"action": "SURRENDER"}
        
        if manager_response.get("status") == "ERROR":
            self.logger.error("Manager reported ERROR. Aborting turn.")
            return None
        
        acting_hero = manager_response.get("hero_name")
        skill = manager_response.get("selected_skill")
        current_ap = manager_response.get("current_ap")
        
        # Validation of manager data
        if current_ap is None or acting_hero is None or skill is None:
            self.logger.error(f"Incomplete manager data: AP={current_ap}, Hero={acting_hero}, Skill={skill}")
            return None
        
        known_enemies = json.dumps(self.known_enemies, indent=2) if self.known_enemies else "No enemies revealed yet."

        try:
            self.logger.info(f"Consulting LLM for attack target. Acting Hero: {acting_hero}")
            decision = self.chain.invoke({
                "known_enemies": known_enemies,
                "acting_hero_name": acting_hero,
                "acting_hero_skill": skill,
            })
            
            self.logger.info(f"Targeting Pos {decision['target_position']} with identity guess: {decision['guessed_identity']}")
            
            return {
                "attacker_team": self.team_name,
                "acting_hero": acting_hero,
                "skill": skill,
                "attacker_ap": current_ap,
                "target_position": decision["target_position"],
                "guessed_identity": decision["guessed_identity"]
            }
        
        except Exception as e:
            self.logger.error(f"Decision logic failed: {str(e)}")
            return None

    def update_intel(self, position, feedback):
        if position not in self.known_enemies:
            self.known_enemies[position] = {"name": "unknown", "health": "unknown", "status": "unknown"}

        # Update revealed identity
        if feedback.get("guess_correct") and feedback.get("actual_identity"):
            self.known_enemies[position]["name"] = feedback["actual_identity"]
            self.logger.info(f"INTEL: Confirmed Pos {position} is {feedback['actual_identity']}")
            
        # Update HP and Status
        if "target_health" in feedback:
            self.known_enemies[position]["health"] = feedback["target_health"]
        
        if "target_status" in feedback:
            self.known_enemies[position]["status"] = feedback["target_status"]
            if feedback["target_status"] == "dead":
                self.logger.info(f"INTEL: Target at Pos {position} confirmed DEAD.")
            
        self.logger.info(f"Current Intel Update for Pos {position}: {self.known_enemies[position]}")

    def receive_hostile_attack(self, attack_payload, my_manager):
        self.logger.info(f"Receiving attack from {attack_payload.get('attacker_team')} on Pos {attack_payload.get('target_position')}")
        feedback = my_manager.process_incoming_attack(attack_payload)

        if feedback is None:
            self.logger.error("Internal Manager failed to process hostile attack.")

        return feedback