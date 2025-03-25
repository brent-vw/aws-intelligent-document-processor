def bedrock_prompt(text):
    
    prompt_template = f"""
    Human: I processed a document using textract. I need to make sense of the results. 
    I need to return the following information for the document:

    - Attribute A
    - Attribute B

    Help me extract the needed information from my textract results.
    Return the results in unformatted JSON array with objects that have the following keys: "AttributeA" (Attribute A), "AttributeB" (Attribute B). Do not include any other text or explanation. Only return the dictionary. Return the dictionary on one line - do not include tabs or newline characters.
    Here is an example:
    <example>
        <input>
            EXAMPLE_INPUT_DATA
        </input>
        <output>
            { "AttributeA": "EXAMPLE_VALUE", "AttributeB": "EXAMPLE_VALUE" }
        </output>
    </example>
    
    My textract results are below:

    {text}
    """
    
    return prompt_template
