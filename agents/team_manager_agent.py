import json
import random
from utils import get_llm_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field

# ANSI color codes for logging hallucinations and errors
RED = "\033[91m"
RESET = "\033[0m"

# class that defines structured output format 
# as a pydantic model for skill
class SkillAttributes(BaseModel):
    damage_amount: int = Field(description="The calculated total damage value. If percentage (e.g 120%), calculate based current attack power.")
    is_aoe: bool = Field(description="True if the skill targets all enemies, False if single target.")
    targets_lowest: bool = Field(description="True if the skill explicitly says it targets the enemy with lowest health.")

class TeamManagerAgent:
    def __init__(self, name, model_name):
        # initializing LLM
        self.name = name
        self.llm = get_llm_agent(model_name, temperature=0.2)
        self.parser = JsonOutputParser()
        
        # agent's memory which will store full hero objects
        #  with their live stats
        self.my_team = {}
        self.system_prompt = """
        This is a two-team battle game with four heroes in each team and you are the Team Manager Agent.
        You are responsible for keeping track of health, attack power, alive or dead, identity revealed or not revealed information for each hero.
        
        Format for each hero is:
        'hero name': {{'passive': "...", 'active': "..."}}
        
        Initially, each hero has 400 health, 200 attack power, "not revealed", and "alive".
        
        YOUR GOAL:
        When asked, you must select ONE alive hero to perform an ACTIVE SKILL.
        1. DO NOT always select same hero by just considering that it will deal massive damage for now, consider using different heroes to strategize your attacks for future.
        2. You CAN NOT select same hero more than twice in succession. 
        3. You need to select each hero at least once in your team.
        4. Internal/Buff: Moves that target a teammate
            - "Infight": Deal 75 damage to a teammate to gain 140 Attack Power.
            - Rule: You cannot target yourself or a dead teammate with Infight.
            - "Subtle" Target self or teammate -> Reduce next damage by 70% & Gain 20 AP.
        
        AVAILABLE MOVES:
        1. **Hero Specific Active Skill**: The unique skill defined in the hero's description.
        2. **Basic Attack**: ANY hero can choose to deal '100%' of their Attack Power to a single enemy.
        
        SKILL TYPES & TARGETING RULES:
        1. Attack Enemy (ACTIVE SKILL):
            - Skills: "Crit", "AOE", "Basic Attack".
            - TARGET: Must be 'enemy'.
        2. Internal/Buff:
            - "Infight", "Subtle".
            - TARGET: Must be 'teammate'.
        
        STRATEGY RULES:
        1. NEVER use "Infight" on a teammate who is already DEAD.
        2. If you are the only one alive, you CANNOT use Infight (no valid target). Attack the enemy instead.
    
        INSTRUCTIONS:
        1. Select the hero and skill according to your current strategy (either their Specific Active OR "Basic Attack").
        2. If using "Basic Attack", set "selected_skill": "Basic Attack" and "target_type": "enemy".
        3. If the skill targets a teammate (like Infight/Subtle), specify "target_type": "teammate" and the "target_id".
        4. If the skill targets an enemy, set "target_type": "enemy".
        5. If the skill targets a teammate, ensure they are ALIVE and selected_hero_id IS NOT SAME AS teammate_target_id (for Infight). 
        
        RESPONSE FORMAT (JSON):
        {{
            "selected_hero_id": <int 0-3>,
            "hero_name": "<name>",
            "selected_skill": "<whole description of the chosen active skill OR 'Basic Attack'>",
            "target_type": <'enemy' or 'teammate'>,
            "teammate_target_id": <int or null>, 
            "reasoning": "<brief strategy explanation>"
        }}         
        
        JSON CONSTRAINTS (CRITICAL):
        1. IF selected_skill is "Basic Attack" -> "target_type": MUST be "enemy"
        2. SKILL CONSISTENCY:
            - IF selected_skill contains "Infight" OR "Subtle" ->  "target_type" MUST be "teammate".
            - IF selected_skill contains "Crit" OR "AOE" -> "target_type" MUST be "enemy".
        3. IF "target_type" is "enemy":
            - Set "teammate_target_id": null
        4. IF "target_type" is "teammate" (e.g., using Infight or Subtle)
            - YOU MUST PROVIDE "teammate_target_id" (int 0-3).
            - "teammate_target_id" CANNOT be null.
            - "teammate_target_id" CANNOT be same as "selected_hero_id" (unless skill allows self-target like Subtle).
        
        Current Team Status: 
        {team_status}
        
        {format_instructions}
        """
        self.team_manager_prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("user", "{input}")
        ])

        self.chain = self.team_manager_prompt | self.llm | self.parser
        
    def initialize_team(self, generated_team_data):
        """
            Takes the raw hero dict from TeamGenerationAgent and initializes
            the game stats (Health=400, Attack=200, IDs 0-3).
        """
        print(f"\n--- Team Manager {self.name}: Initializing Team Stats ---")
        # converting the dict to a list to assign ID indices [0-3]
        hero_names = list(generated_team_data.keys())
        
        for idx, name in enumerate(hero_names):
            hero_info = generated_team_data[name]
            
            # check for scaled stats, otherwise default to standard
            health = hero_info.get("initial_health", 400)
            attack_power = hero_info.get("initial_attack_power", 200)
            
            self.my_team[idx] = {
                "idx": idx,
                "name": name,
                "health": health,
                "attack_power": attack_power, 
                "status": "alive",
                "revealed": False,
                "subtle_shield": False,
                "accumulated_damage": 0,
                "buff_threshold": 200, 
                "passive": hero_info["passive"],
                "active": hero_info["active"]
            }
        
        print(f"--- Team {self.name} ---")
        print(self.my_team)
        
        print(f"Team initialized with {len(self.my_team)} heroes.")
        
    def get_team_status(self):
        """Helper to get list of alive heroes for the LLM context"""
        team_status =  [h for h in self.my_team.values()]
        return json.dumps(team_status, indent=2)
    
    def select_hero_for_turn(self):
        """
        Invokes the LLM to pick a hero to act this turn
        """
        alive_heroes = [h for h in self.my_team.values() if h["status"] == "alive"]
        
        if not alive_heroes:
            print("No alive heroes left! signaling DEFEAT to Team Lead")
            return {"status": "DEFEAT"}
        
        # prepare a string representation of the team state for the LLM
        team_status = self.get_team_status()
        
        try:
            print(f"--- Team Manager: Consulting LLM for Turn Strategy")
            response = self.chain.invoke({
                "team_status": team_status,
                "input": "Select a hero and move.",
                "format_instructions": self.parser.get_format_instructions()
            })
            
            hero_id = response.get("selected_hero_id")
            if (hero_id is not None) and (hero_id in self.my_team):
                response["current_ap"] = self.my_team[hero_id]["attack_power"]
            else:
                # failure case, which should not happen normally
                print(f"Team Manager {self.name} was not able to select hero for attack.")
                return None
            
            print("\n--- Team Manager Decision ---")
            print(response)
            print("\n-----------------------------")
            selected_skill = response.get("selected_skill").lower()
            if response.get("target_type") == "enemy" and ("infight" in selected_skill or "subtle" in selected_skill):
                print(f"{RED}⚠️ ILLEGAL MOVE DETECTED: Agent tried to use Internal Skill '{selected_skill}' on ENEMY.{RESET}") 
                return None
            
            if response.get("target_type") == "teammate":
                self._execute_internal_skill(response)
                # we return a special status so Team Lead knows NOT to attack the enemy this turn 
                response["status"] = "INTERNAL ACTION"
            else:
                # attacking enemy team
                response["status"] = "ACTIVE"    
            
            return response 
        
        except Exception as e:
            print(f"{RED}Error while Team Manager selecting hero: {e}{RESET}")
            return {"status": "ERROR"}            


    def update_hero_stats(self, target_id, damage_amount):
        """
        Updates the state for a hero taking damage.
        Tracks 'alive'/'dead' status.
        """    
        if target_id not in self.my_team:
            print(f"Error: Hero ID {target_id} not found.")
            return

        hero = self.my_team[target_id]
        
        # apply damage
        hero["health"] -= damage_amount
        print(f"Manager: Hero {hero['name']} (ID: {target_id}) took {damage_amount} damage.")
        self._check_death(hero)
        

    def _execute_internal_skill(self, decision):
        """
        Executes skills that affect the own team immediately
        """
        actor_id = decision["selected_hero_id"]
        skill = decision["selected_skill"].lower()
        target_id = decision.get("teammate_target_id")
        
        if target_id is None:
            print(f"{RED}Error: Internal skill requires a target ID.{RESET}")
            return None
        
        target = self.my_team[target_id]
        actor = self.my_team[actor_id]
        
        if "infight" in skill:
            if  target_id == actor_id:
                print(f"{RED}Team Manager Error: Infight cannot target self.{RESET}")
                return None                   
            
            # apply damage to teammate
            damage = 75
            print(f"    > INTERNAL ACTION: {actor['name']} uses Infight on {target['name']}!")
            target["health"] -= damage
            print(f"    > {target['name']} takes {damage} damage. Health {target['health']}")
            self._check_death(target)
            
            # buff actor
            buff = 140
            actor["attack_power"] += buff
            print(f"    > {actor['name']} gains {buff} Attack Power! (New AP: {actor['attack_power']})")            
            
        elif "subtle" in skill:
            # choose a teammate or yourself to reduce damage by 70% and increase AP by 20    
            print(f"   > INTERNAL: {actor['name']} casts SUBTLE on {target['name']}!")
            # apply shield flag
            target["subtle_shield"] = True    
            print(f"    > {target['name']} is now SHIELDED (70% damage reduction on next hit.)")
            
            # buff attack power
            target["attack_power"] += 20
            print(f"    > {target['name']} gains 20 AP! (New AP: {target['attack_power']})")

                            
    def _check_death(self, hero):
        """Helper to handle death logic"""
        if hero["health"] <= 0:
            hero["health"] = 0
            hero["status"] = "dead"
            print(f"    > Hero {hero['name']} has DIED.")
                    
                    
    def _parse_skill_with_llm(self, skill_description, attacker_current_ap, target_current_health):
        """
        Uses the LLM to parse skill text into numbers.
        """
        # injecting the current attack power into prompt rules
        system_prompt = f"""
        You are a Game Rules Engine. 
        Parse the skill description into JSON.
        
        CURRENT BATTLE CONTEXT:
        - The Attacker's Current Attack Power (AP) = {attacker_current_ap}
        - Target's Current Health (HP) = {target_current_health}
        
        RULES: 
        1. **Basic Attack**: If skill name is 'Basic Attack', output damage_amount = {attacker_current_ap}
        2. **Percentages**: If skill says '140% damage' and condition is held (like Infight), output {int(1.4* attacker_current_ap)}           
        3. **Conditionals**: Check conditions like 'If target health < 160'.
            - Example: 'Deal 120 damage. If health < 160, deal 140%'.
            - Since Target health is {target_current_health}, use the correct percentage and calculate.
        4. **Direct Critical Damage**: If skill says '120 CRITICAL DAMAGE' without percentage, output {int(120)}
        5. **Flat Damage**: 'Deal 75 damage' -> 75.
        6. **AOE**: 'All enemies' -> is_aoe: true
        7. **Auto-Target**: If the skill says 'enemy with the lowest health', set targets_lowest: true.
        
        Output JSON: {{{{'damage_amount': float, 'is_aoe': bool, 'targets_lowest': bool}}}}
        """
        
        print(f"Attacker current AP: {attacker_current_ap}")
        print(f"Attacker Skill description: {skill_description}")
        
        parser_prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("user", "Skill Description: {skill_text}\n{format_instructions}")
        ])
        
        chain = parser_prompt | self.llm | JsonOutputParser(pydantic_object=SkillAttributes)
        
        try:
            parsed_skill = chain.invoke({
                "skill_text": skill_description,
                "format_instructions": JsonOutputParser(pydantic_object=SkillAttributes).get_format_instructions()
            })
            
            print(parsed_skill)
            return parsed_skill
        except Exception as e:
            print(f"{RED}Error parsing skill: {e}{RESET}")
            return None    

            
    def process_incoming_attack(self, attack_info):
        """
        Handles an incoming attack.
        
        Args:
            attack_info (dict): Contains target_position, guessed_identity, attacker_ap
        
        Returns: 
            dict: Feedback for the enemy (guess_correct, actual_identity, counter_damage)
        """
        target_pos = attack_info.get("target_position")
        guessed_id = attack_info.get("guessed_identity")
        skill_desc = attack_info.get("skill")
        # getting attacker's stats
        attacker_ap = attack_info.get("attacker_ap")
        
        if target_pos not in self.my_team:
            print(f"{RED}Target position must be a valid position in range int<0-3>.{RESET}")
            return None
        
        target_hero = self.my_team[target_pos]
        actual_identity = target_hero["name"]
        
        print(f"\n[Team Manager {self.name}] Processing Attack on Pos {target_pos} ({actual_identity})...")
        # verifying guess
        guess_correct = (guessed_id.lower() == actual_identity.lower())
        
        if guess_correct:
            if not target_hero["revealed"]:
                print(f"    >  CRITICAL BREACH! Enemy correctly guessed {actual_identity}!")
                target_hero["revealed"] = True
                
                # all alive heroes take 50 damage
                print(" > Applying 50 GLOBAL DAMAGE to team")
                for h in self.my_team.values():
                    if h["status"] == "alive":
                        h["health"] -= 50
                        self._check_death(h)
            else:
                print(f"    > Enemy correctly identified {actual_identity} (Already Revealed). No global damage.")
            
        else: 
            print(f"    > Enemy guessed '{guessed_id}'. Incorrect.")
        
        # passing context so LLM can handle attack
        current_target_hp = target_hero["health"]
        parsed_skill = self._parse_skill_with_llm(skill_desc, attacker_ap, current_target_hp)
        
        if parsed_skill is None:
            print(f"{RED}[{self.name}] Failed to parse incoming skill. Cannot process damage.{RESET}")
            return None
        
        raw_damage = parsed_skill.get("damage_amount")
        is_aoe = parsed_skill.get("is_aoe")        
        
        print(f"    > Team Manager {self.name} Incoming: {raw_damage} damage (AOE: {is_aoe})")
        # determining targets
        targets = []
        if is_aoe:
            targets = [h for h in self.my_team.values() if h["status"] == "alive"]
        
        elif parsed_skill.get("targets_lowest"):
            # the skill 'Crit' overrides the Team Lead's targeting
            alive_mates = [h for h in self.my_team.values() if h["status"] == "alive"]
            if alive_mates:
                # find the hero with lowest HP
                lowest_hp_hero = min(alive_mates, key=lambda x: x["health"])
                targets = [lowest_hp_hero]
                print(f"    > SKILL REDIRECTION {skill_desc[:5]} targets LOWEST HP Hero: {lowest_hp_hero['name']}") 
                
                if lowest_hp_hero["health"] < 160:
                    new_damage = int(attacker_ap * 1.4)
                    if new_damage > raw_damage: 
                        print(f"    > CRIT BOOST! Target HP < 160. Damage Increased: {raw_damage} -> {new_damage}")
                        raw_damage = new_damage                
                        
        else:
            if target_hero["status"] == "alive":
                targets = [target_hero]
        
        
        print(f"    > Incoming: {raw_damage} damage (AOE: {is_aoe})")
        # total damage to be dealt to attacker (if any)
        total_counter_damage = 0
        # applying damage & passives
        for hero in targets:
            damage_to_take = raw_damage
            passive_desc = hero["passive"].lower()

            # Reduce (Nord/Breton): 30% chance to avoid
            if "reduce" in passive_desc and random.random() < 0.30:
                print(f"    > {hero['name']} ACTIVATED 'REDUCE': Dodged!")
                damage_to_take = 0    

            elif "deflect" in passive_desc and damage_to_take > 0:
                print(f"    > {hero['name']} ACTIVATED 'DEFLECT'") 
                self_damage = int(damage_to_take * 0.30)
                share_damage_total = int(damage_to_take * 0.70)

                # distribute to teammates
                alive_mates = [m for m in self.my_team.values() if m["status"] == "alive" and m["idx"] != hero["idx"]]
                if alive_mates:
                    damage_per_mate = share_damage_total // len(alive_mates)
                    for mate in alive_mates:
                        mate["health"] -= damage_per_mate
                        print(f"    -> Teammate {mate['name']} took {damage_per_mate} shared.")
                        self._check_death(mate)
                
                damage_to_take = self_damage
                
            if hero["subtle_shield"] and damage_to_take > 0:
                # reduce the damage by 70% when attacked    
                original_damage = damage_to_take
                damage_to_take = int(damage_to_take * 0.30)
                print(f"    > {hero['name']} consumes SUBTLE SHIELD! Reduced {original_damage} -> {damage_to_take}")
                hero["subtle_shield"] = False # cosume shield on use                
                                
            # apply damage 
            if damage_to_take > 0:
                hero["health"] -= damage_to_take
                print(f"    > {hero['name']} took {damage_to_take} damage. HP: {hero['health']}")
            
            if "deflect" in passive_desc:
                hero["accumulated_damage"] += damage_to_take
                print(f"    > [Redguard Tracker] Accumulated: {hero['accumulated_damage']}/{hero['buff_threshold']}")
                
                if hero["accumulated_damage"] >= hero["buff_threshold"]:
                    hero["attack_power"] += 40
                    hero["buff_threshold"] += 200
                    print(f"    > REDGURAD FRENZY! {hero['name']} gains +40 AP! (NEW AP: {hero['attack_power']})")
                             
            # reaction passives (return info to team lead)
            if "counter" in passive_desc:
                # 30% of 400 is 120 HP
                if any(h["health"] < 120 for h in self.my_team.values() if h["status"] == "alive" and h["idx"] != hero["idx"]):
                    total_counter_damage += 30
                    print(f"    > {hero['name']} ACTIVATED 'COUNTER' (+30 damage)")
            
            if "explode" in passive_desc and damage_to_take > 0:
                 if damage_to_take > 0 and hero["health"] > 0:
                    total_counter_damage += 40
                    print(f"   >  {hero['name']} ACTIVATED 'EXPLODE' (+40 damage)")
                    
                 # checking if health is below 30% of max health
                 if hero["health"] < 120 and hero["health"] > 0:
                     hero["attack_power"] += 15           
                     print(f"   > {hero['name']} is ENRAGED! (+15 Attack Power). Current AP: {hero['attack_power']}")
                                                       
            
            if "heal:" in passive_desc and hero["health"] > 0 and damage_to_take > 0:
                hero["health"] += 20  
                print(f"  > {hero['name']} ACTIVATED 'HEAL' (+20 HP)")
        
            self._check_death(hero)
        
        # collecting all dead heroes to notify enemy
        # which may cover redirection attacks, AOE, and global damage
        all_dead_position = [h["idx"] for h in self.my_team.values() if h["status"] == "dead"]
        
        return {
            "guess_correct": guess_correct,
            "actual_identity": actual_identity if guess_correct else None,
            "counter_damage": total_counter_damage,
            "target_health": target_hero["health"],
            "target_status": target_hero["status"],
            "all_dead_positions": all_dead_position
        }
        
        