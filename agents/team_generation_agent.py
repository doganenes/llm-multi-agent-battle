import logging
import os
import json
from datetime import datetime
from utils import get_llm_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

# ANSI color codes for logging hallucinations and errors
RED = "\033[91m"
RESET = "\033[0m"

class TeamGenerationAgent:
    def __init__(self, name, model_name):
        self.name = name
        # initializing LLM 
        self.llm = get_llm_agent(model_name, temperature=0.2)
        # defining the output structure
        self.parser = JsonOutputParser()
        
        # Setup Internal Logging
        self.logger = self._setup_internal_logger()
        
        # defining the system prompt
        self.system_prompt = """
        This is a two-team battle game with four heroes in each team and you are the Team Generation Agent.
        There are eight types of heroes in the hero pool. Each hero has its initial health, attack power, active ability, and passive ability.
        Your task is to choose four different heroes from a pool of eight heroes according to your team forming strategy.
        
        Format of each hero is given as follows:
        {{
            'Argonian': {{
                'passive': "Counter: Deal 30 damage to the attacker when a teammate's health is below 30%.",
                'active': "AOE: Attacks all enemies for '35%' of its attack point."
            }},
            'Khajit': {{
                'passive': "Counter Deal 30 damage to the attacker when a teammate's health is below '30%'.",
                'active': "Infight: Deal 75 damage on one living teammate and increase your attack points by 140. Notice! You can't attack yourself or a dead teammate!"
            }},
            'Redguard': {{
                'passive': "Deflect: Distribute '70%' damage to teammates and take '30%' damage when attacked. Gains 40 attack points after taking 200 damage accumulated.",
                'active': "Infight: Deal 75 damage on one living teammate and increase your attack points by 140. Notice! You can't attack yourself or a dead teammate!"
            }},
            'Nord': {{
                'passive': "Reduce: There is a '30%' chance to avoid any incoming damage each time.",
                'active': "Crit: Deal 120 CRITICAL damage to enemy."
            }},
            'Breton': {{
                'passive': "Reduce: There is a '30%' chance to avoid any incoming damage each time.",
                'active': "Subtle: Choose a teammate or yourself to reduce the damage by '70%' when attacked, and increase your attack point by 20."
            }},
            'Imperial': {{
                'passive': "Heal: Regain 20 health points if the health is still greater than 0 when attacked.",
                'active': "Infight: Deal 75 damage on one living teammate and increase your attack points by 140. Notice! You can't attack yourself or a dead teammate!", 
            }},
            'Onsimer': {{
                'passive': "Heal: Regain 20 health points if the health is still greater than 0 when attacked.",
                'active': "Crit: Deal 120 CRITICAL damage of your attack power to the enemy with the lowest health. If the target's health is below 160, increase CRITICAL damage to '140%'."
            }},
            'Bosmer': {{
                'passive': "Explode: Deal 40 damage to the source when attacked, but not died. when the health is below '30%', increase its attack points by 15.",
                'active': "Crit: Deal 120 CRITICAL damage of your attack power to the enemy with the lowest health. If the target's health is below 160, increase CRITICAL damage to '140%'."
            }}
        }}
        
        REQUIRED OUTPUT FORMAT (STRICT JSON):
        Return a single JSON dictionary.
        1. KEYS: Must be the Hero Name (e.g., "Argonian", "Nord").
        2. VALUES: Must be a DICTIONARY ({{...}})
        3. VALUE STRUCTURE:
        {{
            "passive": "<copy text exactly from above>",
            "active": "<copy text exactly from above>"
        }}
        
        After you choose four heroes, return them in the above structured format because this team information will be used by Team Manager Agent of your team to keep your team's stats.
        Do not output any markdown code blocks or explanatory text. Just the JSON.
        
        {format_instructions}
        """
    
        # creating prompt template
        self.team_generation_prompt = ChatPromptTemplate.from_messages([
        ("system", self.system_prompt),
        ("user", "{input}")
        ])

        # creating the chain
        self.chain = self.team_generation_prompt | self.llm | self.parser
        
    def _setup_internal_logger(self):
        """Configures logger to save in logs/ directory"""
        if not os.path.exists('logs'):
            os.makedirs('logs')
        
        logger = logging.getLogger(f"Generator_{self.name}")
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            log_file = f"logs/simulation_{datetime.now().strftime('%Y-%m-%d')}.log"
            file_handler = logging.FileHandler(log_file)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        return logger

    def generate_team(self):
        """        
            Invokes the chain to generate a team of 4 heroes
        """
        self.logger.info(f"Team Generation Agent {self.name}: Starting hero selection process.")
        try:
            # injecting format instructions
            response = self.chain.invoke({
                "input": "Generate a team of 4 distinct heroes now.",
                "format_instructions": self.parser.get_format_instructions()
            })
            
            selected_heroes = list(response.keys())
            self.logger.info(f"Successfully generated team for {self.name}: {selected_heroes}")
            return response
            
        except Exception as e:
            self.logger.error(f"Error during team generation for {self.name}: {str(e)}")
            return None